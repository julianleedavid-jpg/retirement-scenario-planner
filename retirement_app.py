from dataclasses import dataclass, field
from datetime import date, timedelta
import json
import uuid
from typing import List, Tuple
import pandas as pd
import requests
import streamlit as st
from streamlit_gsheets import GSheetsConnection


def get_next_tax_year_start(from_date: date = None) -> date:
    if from_date is None:
        from_date = date.today()
    if from_date < date(from_date.year, 4, 6):
        return date(from_date.year, 4, 6)
    return date(from_date.year + 1, 4, 6)


# Configure Streamlit page layout
st.set_page_config(page_title="Joint Retirement Scenario Planner", layout="wide")


# ----------------------------------------------------------------------
# 0. Password Protection Gate
# ----------------------------------------------------------------------

def check_password():
    """Returns True if the user enters the correct password."""
    def password_entered():
        if st.session_state["password_input"] == st.secrets.get("app_password", ""):
            st.session_state["password_correct"] = True
            del st.session_state["password_input"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("🔒 Enter Access Password:", type="password", on_change=password_entered, key="password_input")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("🔒 Enter Access Password:", type="password", on_change=password_entered, key="password_input")
        st.error("❌ Incorrect password")
        return False
    else:
        return True


if not check_password():
    st.stop()


st.title("📈 Joint Retirement Forecast & Dual-Drawdown Engine")


# ----------------------------------------------------------------------
# 1. Full Data Structures for Joint Profiles
# ----------------------------------------------------------------------

@dataclass
class PotConfig:
    balance: float
    annual_return: float
    monthly_contrib: float = 0.0


@dataclass
class LumpSum:
    amount: float = 0.0
    injection_date: date = field(default_factory=get_next_tax_year_start)
    target_pot: str = "S&S ISA"


@dataclass
class PersonProfile:
    name: str
    dob: date
    ret_age: int
    sipp: PotConfig
    workplace_pension_total: float
    workplace_pension_return: float
    workplace_pension_contrib: float
    isa: PotConfig
    other_investment: PotConfig
    has_state_pension: bool
    state_pension_age: int
    state_pension_amount: float
    state_pension_growth: float = 0.025
    annuity_annual: float = 0.0
    annuity_start_age: int = 65
    annuity_npa: int = 65
    annuity_type: str = "Inflation-Linked (RPI/CPI)"
    apply_db_early_reduction: bool = True
    has_nuvos_pension: bool = False
    nuvos_annual: float = 0.0
    nuvos_baseline_date: date = field(default_factory=lambda: date(2025, 3, 31))
    nuvos_npa: int = 65
    nuvos_pause_enabled: bool = True
    nuvos_pause_date: date = field(default_factory=get_next_tax_year_start)
    nuvos_salary: float = 0.0
    nuvos_accrual_rate: float = 2.3
    apply_nuvos_early_reduction: bool = True
    lump_sums: List[LumpSum] = field(default_factory=list)

    workplace_tax_free: PotConfig = field(init=False)
    workplace_taxable: PotConfig = field(init=False)

    def __post_init__(self):
        self.workplace_tax_free = PotConfig(
            balance=self.workplace_pension_total * 0.25,
            annual_return=self.workplace_pension_return,
            monthly_contrib=self.workplace_pension_contrib * 0.25,
        )
        self.workplace_taxable = PotConfig(
            balance=self.workplace_pension_total * 0.75,
            annual_return=self.workplace_pension_return,
            monthly_contrib=self.workplace_pension_contrib * 0.75,
        )


@dataclass
class JointScenario:
    name: str
    p1: PersonProfile
    p2: PersonProfile
    household_monthly_income: float
    inflation_rate: float = 0.03
    crash_pct: float = 0.0
    crash_date: date = field(default_factory=get_next_tax_year_start)


# ----------------------------------------------------------------------
# 2. Joint Calculation & Dual-Drawdown Engine
# ----------------------------------------------------------------------

class JointRetirementEngine:
    PERSONAL_ALLOWANCE = 12570.0
    BASIC_TAX_RATE = 0.20

    def __init__(self, joint_scenario: JointScenario):
        self.scenario = joint_scenario
        self.p1 = joint_scenario.p1
        self.p2 = joint_scenario.p2

    @staticmethod
    def _get_daily_rate(annual_rate: float) -> float:
        return (1.0 + annual_rate) ** (1.0 / 365.0) - 1.0

    @staticmethod
    def _get_tax_year(d: date) -> str:
        if d >= date(d.year, 4, 6):
            return f"{d.year}/{str(d.year + 1)[2:]}"
        return f"{d.year - 1}/{str(d.year)[2:]}"

    def run_joint_simulation(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        start_date = date.today()
        try:
            end_date = date(self.p1.dob.year + 100, self.p1.dob.month, self.p1.dob.day)
        except ValueError:
            end_date = date(self.p1.dob.year + 100, 2, 28)

        # Track P1 balances (Julian)
        p1_sipp = self.p1.sipp.balance
        p1_wp_taxable = self.p1.workplace_taxable.balance
        p1_wp_taxfree = self.p1.workplace_tax_free.balance
        p1_isa = self.p1.isa.balance
        p1_other = self.p1.other_investment.balance

        # Track P2 balances (Karen)
        p2_sipp = self.p2.sipp.balance
        p2_wp_taxable = self.p2.workplace_taxable.balance
        p2_wp_taxfree = self.p2.workplace_tax_free.balance
        p2_isa = self.p2.isa.balance
        p2_other = self.p2.other_investment.balance

        current_date = start_date
        daily_records = []

        p1_taxable_this_year = 0.0
        p2_taxable_this_year = 0.0
        last_tax_year = self._get_tax_year(current_date)

        while current_date <= end_date:
            p1_age = current_date.year - self.p1.dob.year - ((current_date.month, current_date.day) < (self.p1.dob.month, self.p1.dob.day))
            p2_age = current_date.year - self.p2.dob.year - ((current_date.month, current_date.day) < (self.p2.dob.month, self.p2.dob.day))

            p1_retired = p1_age >= self.p1.ret_age
            p2_retired = p2_age >= self.p2.ret_age
            both_retired = p1_retired and p2_retired

            current_tax_year = self._get_tax_year(current_date)
            if current_tax_year != last_tax_year:
                p1_taxable_this_year = 0.0
                p2_taxable_this_year = 0.0
                last_tax_year = current_tax_year

            # Monthly pre-retirement contributions
            if current_date.day == 1:
                if not p1_retired:
                    p1_sipp += self.p1.sipp.monthly_contrib
                    p1_wp_taxable += self.p1.workplace_taxable.monthly_contrib
                    p1_wp_taxfree += self.p1.workplace_tax_free.monthly_contrib
                    p1_isa += self.p1.isa.monthly_contrib
                    p1_other += self.p1.other_investment.monthly_contrib
                if not p2_retired:
                    p2_sipp += self.p2.sipp.monthly_contrib
                    p2_wp_taxable += self.p2.workplace_taxable.monthly_contrib
                    p2_wp_taxfree += self.p2.workplace_tax_free.monthly_contrib
                    p2_isa += self.p2.isa.monthly_contrib
                    p2_other += self.p2.other_investment.monthly_contrib

            # Daily Compound Return Growth
            p1_sipp *= (1.0 + self._get_daily_rate(self.p1.sipp.annual_return))
            p1_wp_taxable *= (1.0 + self._get_daily_rate(self.p1.workplace_pension_return))
            p1_wp_taxfree *= (1.0 + self._get_daily_rate(self.p1.workplace_pension_return))
            p1_isa *= (1.0 + self._get_daily_rate(self.p1.isa.annual_return))
            p1_other *= (1.0 + self._get_daily_rate(self.p1.other_investment.annual_return))

            p2_sipp *= (1.0 + self._get_daily_rate(self.p2.sipp.annual_return))
            p2_wp_taxable *= (1.0 + self._get_daily_rate(self.p2.workplace_pension_return))
            p2_wp_taxfree *= (1.0 + self._get_daily_rate(self.p2.workplace_pension_return))
            p2_isa *= (1.0 + self._get_daily_rate(self.p2.isa.annual_return))
            p2_other *= (1.0 + self._get_daily_rate(self.p2.other_investment.annual_return))

            # Monthly Drawdown logic executed on 1st of each month
            if (p1_retired or p2_retired) and current_date.day == 1:
                years_since_start = current_date.year - start_date.year
                target_net_monthly = self.scenario.household_monthly_income * ((1.0 + self.scenario.inflation_rate) ** years_since_start)

                # Guaranteed DB/State Pension incomes
                g_p1 = self._get_monthly_guaranteed(self.p1, p1_age, years_since_start)
                g_p2 = self._get_monthly_guaranteed(self.p2, p2_age, years_since_start)

                p1_taxable_this_year += g_p1
                p2_taxable_this_year += g_p2

                guaranteed_tot = g_p1 + g_p2
                needed_net = max(0.0, target_net_monthly - guaranteed_tot)

                # Tax-Optimized Dual Drawdowns
                if needed_net > 0:
                    # Priority 1: Fill Personal Allowances (£12,570) tax-free for active retirees
                    allow_p1_rem = max(0.0, self.PERSONAL_ALLOWANCE - p1_taxable_this_year)
                    allow_p2_rem = max(0.0, self.PERSONAL_ALLOWANCE - p2_taxable_this_year)

                    if allow_p1_rem > 0 and p1_retired:
                        draw_req = min(needed_net / 2.0 if both_retired else needed_net, allow_p1_rem)
                        p1_sipp, p1_wp_taxable, p1_taxable_this_year, needed_net = self._draw_taxable_pot(
                            p1_sipp, p1_wp_taxable, draw_req, p1_taxable_this_year, needed_net
                        )

                    if allow_p2_rem > 0 and p2_retired:
                        draw_req = min(needed_net / 2.0 if both_retired else needed_net, allow_p2_rem)
                        p2_sipp, p2_wp_taxable, p2_taxable_this_year, needed_net = self._draw_taxable_pot(
                            p2_sipp, p2_wp_taxable, draw_req, p2_taxable_this_year, needed_net
                        )

                    # Priority 2: Simultaneous draw down from ISAs
                    if needed_net > 0:
                        if both_retired:
                            draw_p1 = min(p1_isa, needed_net / 2.0)
                            draw_p2 = min(p2_isa, needed_net - draw_p1)
                            p1_isa -= draw_p1
                            p2_isa -= draw_p2
                            needed_net -= (draw_p1 + draw_p2)
                        elif p1_retired and p1_isa > 0:
                            draw = min(p1_isa, needed_net)
                            p1_isa -= draw
                            needed_net -= draw
                        elif p2_retired and p2_isa > 0:
                            draw = min(p2_isa, needed_net)
                            p2_isa -= draw
                            needed_net -= draw

            p1_tot = p1_sipp + p1_wp_taxable + p1_wp_taxfree + p1_isa + p1_other
            p2_tot = p2_sipp + p2_wp_taxable + p2_wp_taxfree + p2_isa + p2_other
            total_portfolio = p1_tot + p2_tot

            daily_records.append({
                "date": current_date,
                "p1_age": p1_age,
                "p2_age": p2_age,
                "dual_age_label": f"Julian Age {p1_age} / Karen Age {p2_age}",
                "total_portfolio": int(round(total_portfolio)),
                "p1_portfolio": int(round(p1_tot)),
                "p2_portfolio": int(round(p2_tot)),
            })
            current_date += timedelta(days=1)

        df = pd.DataFrame(daily_records)
        annual_df = df.groupby(["p1_age", "p2_age"]).agg({
            "dual_age_label": "last",
            "total_portfolio": "last",
            "p1_portfolio": "last",
            "p2_portfolio": "last",
        }).reset_index()

        return df, annual_df

    @staticmethod
    def _get_monthly_guaranteed(p: PersonProfile, age: int, years_since_start: int) -> float:
        monthly = 0.0
        if p.has_state_pension and age >= p.state_pension_age:
            annual_sp = p.state_pension_amount * ((1.0 + p.state_pension_growth) ** years_since_start)
            monthly += annual_sp / 12.0
        if p.has_nuvos_pension and age >= p.ret_age:
            monthly += (p.nuvos_annual * ((1.0 + 0.03) ** years_since_start)) / 12.0
        return monthly

    @staticmethod
    def _draw_taxable_pot(sipp: float, wp_taxable: float, requested: float, tax_year_acc: float, needed_net: float):
        tot = sipp + wp_taxable
        if tot <= 0 or requested <= 0:
            return sipp, wp_taxable, tax_year_acc, needed_net
        draw = min(tot, requested)
        s_share = sipp / tot
        wp_share = wp_taxable / tot
        sipp -= draw * s_share
        wp_taxable -= draw * wp_share
        return sipp, wp_taxable, tax_year_acc + draw, needed_net - draw


# ----------------------------------------------------------------------
# 3. Streamlit Sidebar & Profile Setup
# ----------------------------------------------------------------------

st.sidebar.header("⚙️ Joint Scenario Setup")

household_income = st.sidebar.number_input("Desired Monthly Household Income (£)", min_value=500.0, value=3500.0, step=100.0)

st.sidebar.markdown("---")
st.sidebar.subheader("👤 Julian Setup")
p1_ret_age = st.sidebar.number_input("Julian Target Retirement Age", min_value=50, max_value=75, value=62)
p1_sipp_bal = st.sidebar.number_input("Julian SIPP (£)", value=52500.0, step=1000.0)
p1_wp_bal = st.sidebar.number_input("Julian Workplace Pension (£)", value=250000.0, step=5000.0)
p1_isa_bal = st.sidebar.number_input("Julian S&S ISA (£)", value=105000.0, step=5000.0)

st.sidebar.markdown("---")
st.sidebar.subheader("👤 Karen Setup")
p2_ret_age = st.sidebar.number_input("Karen Target Retirement Age", min_value=50, max_value=75, value=57)
p2_nuvos_annual = st.sidebar.number_input("Karen Nuvos Annual Pension (£)", value=15929.31, step=500.0)
p2_isa_bal = st.sidebar.number_input("Karen S&S ISA (£)", value=10000.0, step=1000.0)

# Instantiate Profiles
julian_profile = PersonProfile(
    name="Julian",
    dob=date(1969, 12, 1),
    ret_age=int(p1_ret_age),
    sipp=PotConfig(balance=p1_sipp_bal, annual_return=0.07, monthly_contrib=500.0),
    workplace_pension_total=p1_wp_bal,
    workplace_pension_return=0.07,
    workplace_pension_contrib=700.0,
    isa=PotConfig(balance=p1_isa_bal, annual_return=0.07, monthly_contrib=0.0),
    other_investment=PotConfig(balance=57000.0, annual_return=0.03, monthly_contrib=0.0),
    has_state_pension=True,
    state_pension_age=67,
    state_pension_amount=12548.0,
)

karen_profile = PersonProfile(
    name="Karen",
    dob=date(1980, 10, 16),
    ret_age=int(p2_ret_age),
    sipp=PotConfig(balance=0.0, annual_return=0.07, monthly_contrib=0.0),
    workplace_pension_total=0.0,
    workplace_pension_return=0.07,
    workplace_pension_contrib=0.0,
    isa=PotConfig(balance=p2_isa_bal, annual_return=0.07, monthly_contrib=0.0),
    other_investment=PotConfig(balance=0.0, annual_return=0.03, monthly_contrib=0.0),
    has_state_pension=True,
    state_pension_age=67,
    state_pension_amount=12548.0,
    has_nuvos_pension=True,
    nuvos_annual=p2_nuvos_annual,
)

joint_scenario = JointScenario(
    name="Base Joint Scenario",
    p1=julian_profile,
    p2=karen_profile,
    household_monthly_income=household_income,
)

# Run Engine
engine = JointRetirementEngine(joint_scenario)
daily_df, annual_df = engine.run_joint_simulation()

# ----------------------------------------------------------------------
# 4. Main Dashboard Output
# ----------------------------------------------------------------------

col1, col2, col3 = st.columns(3)
col1.metric("Julian Retirement Age", f"Age {p1_ret_age}")
col2.metric("Karen Retirement Age", f"Age {p2_ret_age}")
col3.metric("Peak Portfolio Value", f"£{int(round(annual_df['total_portfolio'].max())):,}")

st.markdown("---")

st.subheader("📊 Household Portfolio Trajectory")
st.line_chart(
    annual_df,
    x="dual_age_label",
    y=["total_portfolio", "p1_portfolio", "p2_portfolio"],
)

st.subheader("📋 Household Balances Table (Side-by-Side Ages)")
st.dataframe(
    annual_df,
    column_config={
        "dual_age_label": st.column_config.TextColumn("Individual Ages (Side-by-Side)"),
        "total_portfolio": st.column_config.NumberColumn("Combined Portfolio", format="£%,d"),
        "p1_portfolio": st.column_config.NumberColumn("Julian Portfolio", format="£%,d"),
        "p2_portfolio": st.column_config.NumberColumn("Karen Portfolio", format="£%,d"),
    },
    use_container_width=True,
    height=600,
)
