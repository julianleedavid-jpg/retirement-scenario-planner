from dataclasses import dataclass, field
from datetime import date, timedelta
import json
import os
from typing import List, Tuple
import pandas as pd
import streamlit as st

JSON_FILE = "scenarios.json"


def get_next_tax_year_start(from_date: date = None) -> date:
    if from_date is None:
        from_date = date.today()
    if from_date < date(from_date.year, 4, 6):
        return date(from_date.year, 4, 6)
    return date(from_date.year + 1, 4, 6)


# Configure Streamlit page layout
st.set_page_config(page_title="Retirement Scenario Planner", layout="wide")


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


st.title("📈 Retirement Forecast & Drawdown Engine")

# ----------------------------------------------------------------------
# 1. JSON Persistence & Default Scenarios
# ----------------------------------------------------------------------

DEFAULT_PROFILES = {
    "Base Case": {
        "dob": date(1969, 12, 1),
        "ret_age": 62,
        "monthly_inc": 2500.0,
        "increased_monthly_inc": 0.0,
        "increase_date": get_next_tax_year_start(),
        "reduced_monthly_inc": 2500.0,
        "reduced_inc_age": 80,
        "inflation_rate": 3.0,
        "sipp_bal": 52500.0,
        "sipp_ret": 7.0,
        "sipp_contrib": 500.0,
        "wp_bal": 250000.0,
        "wp_ret": 7.0,
        "wp_contrib": 700.0,
        "isa_bal": 105000.0,
        "isa_ret": 7.0,
        "isa_contrib": 0.0,
        "other_bal": 57000.0,
        "other_ret": 3.0,
        "other_contrib": 0.0,
        "has_state_pension": True,
        "state_pension_age": 67,
        "state_pension_amount": 12548.0,
        "state_pension_growth": 2.5,
        "annuity_annual": 0.0,
        "annuity_cost": 0.0,
        "annuity_start_age": 62,
        "inflate_annuity_to_start": False,
        "lump_sum_1_amt": 0.0,
        "lump_sum_1_date": get_next_tax_year_start(),
        "lump_sum_1_pot": "S&S ISA",
        "lump_sum_2_amt": 0.0,
        "lump_sum_2_date": get_next_tax_year_start(),
        "lump_sum_2_pot": "S&S ISA",
        "lump_sum_3_amt": 0.0,
        "lump_sum_3_date": get_next_tax_year_start(),
        "lump_sum_3_pot": "S&S ISA",
        "crash_pct": 0.0,
        "crash_date": get_next_tax_year_start(),
        "view_mode": "Tax Year",
        "notes": "",
        "budget_items": [
            {"category": "Housing / Council Tax", "amount": 800.0},
            {"category": "Utilities & Broadband", "amount": 250.0},
            {"category": "Groceries", "amount": 400.0},
            {"category": "Transport & Fuel", "amount": 200.0},
            {"category": "Leisure & Holidays", "amount": 350.0},
        ],
    },
    "Karen": {
        "dob": date(1980, 10, 16),
        "ret_age": 65,
        "monthly_inc": 2500.0,
        "increased_monthly_inc": 0.0,
        "increase_date": get_next_tax_year_start(),
        "reduced_monthly_inc": 2500.0,
        "reduced_inc_age": 80,
        "inflation_rate": 3.0,
        "sipp_bal": 0.0,
        "sipp_ret": 7.0,
        "sipp_contrib": 0.0,
        "wp_bal": 0.0,
        "wp_ret": 7.0,
        "wp_contrib": 0.0,
        "isa_bal": 0.0,
        "isa_ret": 7.0,
        "isa_contrib": 0.0,
        "other_bal": 0.0,
        "other_ret": 3.0,
        "other_contrib": 0.0,
        "has_state_pension": True,
        "state_pension_age": 67,
        "state_pension_amount": 12548.0,
        "state_pension_growth": 2.5,
        "annuity_annual": 15929.0,  # Accrued RCPS Nuvos DB Pension as of 2025
        "annuity_cost": 0.0,
        "annuity_start_age": 65, # Nuvos Normal Pension Age
        "inflate_annuity_to_start": False,
        "lump_sum_1_amt": 0.0,
        "lump_sum_1_date": get_next_tax_year_start(),
        "lump_sum_1_pot": "S&S ISA",
        "lump_sum_2_amt": 0.0,
        "lump_sum_2_date": get_next_tax_year_start(),
        "lump_sum_2_pot": "S&S ISA",
        "lump_sum_3_amt": 0.0,
        "lump_sum_3_date": get_next_tax_year_start(),
        "lump_sum_3_pot": "S&S ISA",
        "crash_pct": 0.0,
        "crash_date": get_next_tax_year_start(),
        "view_mode": "Tax Year",
        "notes": "",
        "budget_items": [
            {"category": "Housing / Council Tax", "amount": 700.0},
            {"category": "Utilities & Broadband", "amount": 200.0},
            {"category": "Groceries", "amount": 350.0},
            {"category": "Transport & Fuel", "amount": 150.0},
        ],
    },
}


def serialize_scenario(scen_dict: dict) -> dict:
    serialized = {}
    for k, v in scen_dict.items():
        if isinstance(v, date):
            serialized[k] = v.isoformat()
        else:
            serialized[k] = v
    return serialized


def deserialize_scenario(scen_dict: dict) -> dict:
    deserialized = {}
    for k, v in scen_dict.items():
        if isinstance(v, str):
            try:
                deserialized[k] = date.fromisoformat(v)
            except ValueError:
                deserialized[k] = v
        else:
            deserialized[k] = v
    # Ensure budget items exist for loaded profiles
    if "budget_items" not in deserialized:
        deserialized["budget_items"] = []
    return deserialized


def load_scenarios() -> dict:
    scenarios = {k: v.copy() for k, v in DEFAULT_PROFILES.items()}
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r") as f:
                data = json.load(f)
            loaded = {name: deserialize_scenario(scen) for name, scen in data.items()}
            scenarios.update(loaded)
        except Exception:
            pass
    return scenarios


def save_scenarios():
    data = {
        name: serialize_scenario(scen)
        for name, scen in st.session_state.scenarios.items()
    }
    with open(JSON_FILE, "w") as f:
        json.dump(data, f, indent=4)


# Initialize Session State
if "scenarios" not in st.session_state:
    st.session_state.scenarios = load_scenarios()

if "active_scenario_name" not in st.session_state or st.session_state.active_scenario_name not in st.session_state.scenarios:
    st.session_state.active_scenario_name = list(st.session_state.scenarios.keys())[0]


# ----------------------------------------------------------------------
# 2. Data Models
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
class Scenario:
    name: str
    sipp: PotConfig
    workplace_pension_total: float
    workplace_pension_return: float
    workplace_pension_contrib: float
    isa: PotConfig
    other_investment: PotConfig
    has_state_pension: bool
    state_pension_age: int
    state_pension_amount: float
    lump_sums: List[LumpSum] = field(default_factory=list)
    state_pension_growth: float = 0.025
    inflation_rate: float = 0.03
    annuity_annual: float = 0.0
    annuity_cost: float = 0.0
    annuity_start_age: int = 65
    inflate_annuity_to_start: bool = False
    increased_monthly_inc: float = 0.0
    increase_date: date = field(default_factory=get_next_tax_year_start)
    reduced_monthly_inc: float = 2500.0
    reduced_inc_age: int = 80
    crash_pct: float = 0.0
    crash_date: date = field(default_factory=get_next_tax_year_start)

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


# ----------------------------------------------------------------------
# 3. Calculation & Drawdown Engine
# ----------------------------------------------------------------------

class RetirementEngine:
    PERSONAL_ALLOWANCE = 12570.0
    BASIC_TAX_RATE = 0.20
    ISA_ANNUAL_ALLOWANCE = 20000.0

    def __init__(
        self,
        dob: date,
        retirement_age: int,
        monthly_income: float,
        scenario: Scenario,
    ):
        self.dob = dob
        self.retirement_age = retirement_age
        self.monthly_income = monthly_income
        self.scenario = scenario

    @staticmethod
    def _get_daily_rate(annual_rate: float) -> float:
        return (1.0 + annual_rate) ** (1.0 / 365.0) - 1.0

    @staticmethod
    def _calculate_age(dob: date, current_date: date) -> int:
        return (
            current_date.year
            - dob.year
            - ((current_date.month, current_date.day) < (dob.month, dob.day))
        )

    @staticmethod
    def _get_tax_year(d: date) -> str:
        if d >= date(d.year, 4, 6):
            return f"{d.year}/{str(d.year + 1)[2:]}"
        return f"{d.year - 1}/{str(d.year)[2:]}"

    def run_simulation(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        start_date = date.today()

        try:
            target_100_date = date(self.dob.year + 100, self.dob.month, self.dob.day)
        except ValueError:
            target_100_date = date(self.dob.year + 100, 2, 28)

        # Derive exact annuity start date from annuity_start_age
        try:
            annuity_start_date = date(self.dob.year + self.scenario.annuity_start_age, self.dob.month, self.dob.day)
        except ValueError:
            annuity_start_date = date(self.dob.year + self.scenario.annuity_start_age, 2, 28)

        sipp = self.scenario.sipp.balance
        wp_taxable = self.scenario.workplace_taxable.balance
        wp_tax_free = self.scenario.workplace_tax_free.balance
        isa = self.scenario.isa.balance
        other = self.scenario.other_investment.balance
        cumulative_deficit = 0.0

        daily_records = []
        current_date = start_date
        taxable_income_this_tax_year = 0.0
        isa_credited_this_tax_year = 0.0
        last_tax_year = self._get_tax_year(current_date)
        annuity_purchased = False
        crash_applied = False
        crash_active_until = None
        crash_capped_income = None
        lump_sums_applied = [False] * len(self.scenario.lump_sums)

        # Pre-calculate base starting annuity at Start Date if inflation toggle is checked
        base_annuity = self.scenario.annuity_annual
        if self.scenario.inflate_annuity_to_start and annuity_start_date > start_date:
            years_to_start = (annuity_start_date - start_date).days / 365.25
            base_annuity *= ((1.0 + self.scenario.inflation_rate) ** max(0.0, years_to_start))

        while current_date <= target_100_date:
            age = self._calculate_age(self.dob, current_date)
            is_retired = age >= self.retirement_age
            current_tax_year = self._get_tax_year(current_date)

            if current_tax_year != last_tax_year:
                taxable_income_this_tax_year = 0.0
                isa_credited_this_tax_year = 0.0
                last_tax_year = current_tax_year

            # Evaluate active annual annuity amount every day once target annuity start age reached
            current_annual_annuity = 0.0
            if current_date >= annuity_start_date and base_annuity > 0:
                years_since_annuity = current_date.year - annuity_start_date.year - (
                    (current_date.month, current_date.day) < (annuity_start_date.month, annuity_start_date.day)
                )
                current_annual_annuity = base_annuity * (
                    (1.0 + self.scenario.inflation_rate) ** max(0, years_since_annuity)
                )

            # Apply Lump Sum Injections / Withdrawals with waterfall cascade rules
            for idx, ls in enumerate(self.scenario.lump_sums):
                if not lump_sums_applied[idx] and ls.amount != 0 and current_date >= ls.injection_date:
                    if ls.amount > 0:
                        # Positive injection handling
                        if ls.target_pot == "SIPP":
                            sipp += ls.amount
                        elif ls.target_pot == "Private Pension":
                            wp_tax_free += ls.amount * 0.25
                            wp_taxable += ls.amount * 0.75
                        elif ls.target_pot == "S&S ISA":
                            isa += ls.amount
                        elif ls.target_pot == "Other Investment":
                            other += ls.amount
                    else:
                        # Negative withdrawal handling with waterfall spillover
                        rem_withdrawal = abs(ls.amount)
                        
                        def draw_from_pot(current_bal, requested):
                            possible = min(current_bal, requested)
                            return current_bal - possible, requested - possible

                        if ls.target_pot == "SIPP":
                            sipp, rem_withdrawal = draw_from_pot(sipp, rem_withdrawal)
                            if rem_withdrawal > 0:
                                other, rem_withdrawal = draw_from_pot(other, rem_withdrawal)
                            if rem_withdrawal > 0:
                                total_wp = wp_taxable + wp_tax_free
                                total_wp, rem_withdrawal = draw_from_pot(total_wp, rem_withdrawal)
                                wp_taxable = total_wp * 0.75
                                wp_tax_free = total_wp * 0.25

                        elif ls.target_pot == "Other Investment":
                            other, rem_withdrawal = draw_from_pot(other, rem_withdrawal)
                            if rem_withdrawal > 0:
                                sipp, rem_withdrawal = draw_from_pot(sipp, rem_withdrawal)
                            if rem_withdrawal > 0:
                                total_wp = wp_taxable + wp_tax_free
                                total_wp, rem_withdrawal = draw_from_pot(total_wp, rem_withdrawal)
                                wp_taxable = total_wp * 0.75
                                wp_tax_free = total_wp * 0.25

                        elif ls.target_pot == "Private Pension":
                            total_wp = wp_taxable + wp_tax_free
                            total_wp, rem_withdrawal = draw_from_pot(total_wp, rem_withdrawal)
                            wp_taxable = total_wp * 0.75
                            wp_tax_free = total_wp * 0.25
                            if rem_withdrawal > 0:
                                other, rem_withdrawal = draw_from_pot(other, rem_withdrawal)
                            if rem_withdrawal > 0:
                                sipp, rem_withdrawal = draw_from_pot(sipp, rem_withdrawal)

                        elif ls.target_pot == "S&S ISA":
                            isa, rem_withdrawal = draw_from_pot(isa, rem_withdrawal)

                    lump_sums_applied[idx] = True

            # Apply Market Crash
            if (
                not crash_applied
                and self.scenario.crash_pct > 0
                and current_date >= self.scenario.crash_date
            ):
                drop_factor = 1.0 - (self.scenario.crash_pct / 100.0)
                sipp *= drop_factor
                wp_taxable *= drop_factor
                wp_tax_free *= drop_factor
                isa *= drop_factor
                crash_applied = True

                try:
                    crash_active_until = date(
                        self.scenario.crash_date.year + 2,
                        self.scenario.crash_date.month,
                        self.scenario.crash_date.day,
                    )
                except ValueError:
                    crash_active_until = date(
                        self.scenario.crash_date.year + 2, 2, 28
                    )

                if self.scenario.crash_pct > 5.0:
                    years_to_crash = self.scenario.crash_date.year - start_date.year - (
                        (self.scenario.crash_date.month, self.scenario.crash_date.day) < (start_date.month, start_date.day)
                    )
                    annual_sp_at_crash = self.scenario.state_pension_amount * (
                        (1.0 + self.scenario.state_pension_growth) ** max(0, years_to_crash)
                    )
                    crash_capped_income = annual_sp_at_crash / 12.0

            # Deduct Annuity Purchase Cost
            if current_date >= annuity_start_date and not annuity_purchased:
                cost_rem = self.scenario.annuity_cost
                if cost_rem > 0:
                    draw_other = min(other, cost_rem)
                    other -= draw_other
                    cost_rem -= draw_other

                    if cost_rem > 0:
                        tot_pension = sipp + wp_taxable + wp_tax_free
                        draw_pension = min(tot_pension, cost_rem)
                        if draw_pension > 0 and tot_pension > 0:
                            s_share = sipp / tot_pension
                            wpt_share = wp_taxable / tot_pension
                            wptf_share = wp_tax_free / tot_pension

                            sipp -= draw_pension * s_share
                            wp_taxable -= draw_pension * wpt_share
                            wp_tax_free -= draw_pension * wptf_share
                            cost_rem -= draw_pension

                    if cost_rem > 0:
                        draw_isa = min(isa, cost_rem)
                        isa -= draw_isa
                        cost_rem -= draw_isa

                annuity_purchased = True

            # Pre-Retirement Monthly Contributions
            if not is_retired and current_date.day == 1:
                sipp += self.scenario.sipp.monthly_contrib
                wp_taxable += self.scenario.workplace_taxable.monthly_contrib
                wp_tax_free += self.scenario.workplace_tax_free.monthly_contrib
                isa += self.scenario.isa.monthly_contrib
                other += self.scenario.other_investment.monthly_contrib

            # Daily Growth
            sipp *= 1.0 + self._get_daily_rate(self.scenario.sipp.annual_return)
            wp_taxable *= 1.0 + self._get_daily_rate(
                self.scenario.workplace_taxable.annual_return
            )
            wp_tax_free *= 1.0 + self._get_daily_rate(
                self.scenario.workplace_tax_free.annual_return
            )
            isa *= 1.0 + self._get_daily_rate(self.scenario.isa.annual_return)
            other *= 1.0 + self._get_daily_rate(
                self.scenario.other_investment.annual_return
            )

            monthly_drawn_from_pots = 0.0
            state_pension_monthly = 0.0
            annuity_monthly = 0.0
            tax_paid = 0.0

            years_since_start = current_date.year - start_date.year - (
                (current_date.month, current_date.day) < (start_date.month, start_date.day)
            )

            in_crash_window = (
                crash_applied
                and crash_active_until is not None
                and current_date < crash_active_until
            )

            if in_crash_window and self.scenario.crash_pct > 5.0 and crash_capped_income is not None:
                inflated_monthly_income = crash_capped_income
            else:
                if age >= self.scenario.reduced_inc_age:
                    base_target_income = self.scenario.reduced_monthly_inc
                elif (
                    self.scenario.increased_monthly_inc > 0
                    and current_date >= self.scenario.increase_date
                ):
                    base_target_income = self.scenario.increased_monthly_inc
                else:
                    base_target_income = self.monthly_income

                inflated_monthly_income = base_target_income * (
                    (1.0 + self.scenario.inflation_rate) ** years_since_start
                )

            # Sweep excess "Other Investment" above 2x desired annual income into S&S ISA on the 1st of each month
            if current_date.day == 1:
                current_desired_annual = inflated_monthly_income * 12.0
                threshold_other = 2.0 * current_desired_annual
                if other > threshold_other:
                    excess_other = other - threshold_other
                    isa_allowance_rem = max(0.0, self.ISA_ANNUAL_ALLOWANCE - isa_credited_this_tax_year)
                    to_isa_from_other = min(excess_other, isa_allowance_rem)
                    if to_isa_from_other > 0:
                        other -= to_isa_from_other
                        isa += to_isa_from_other
                        isa_credited_this_tax_year += to_isa_from_other

            # Post-Retirement Drawdown Execution (Runs on the 1st of each month)
            if is_retired and current_date.day == 1:
                if current_annual_annuity > 0:
                    annuity_monthly = current_annual_annuity / 12.0
                    taxable_income_this_tax_year += annuity_monthly

                if (
                    self.scenario.has_state_pension
                    and age >= self.scenario.state_pension_age
                ):
                    inflated_state_pension_annual = self.scenario.state_pension_amount * (
                        (1.0 + self.scenario.state_pension_growth) ** years_since_start
                    )
                    state_pension_monthly = inflated_state_pension_annual / 12.0
                    taxable_income_this_tax_year += state_pension_monthly

                guaranteed_monthly_income = annuity_monthly + state_pension_monthly

                if guaranteed_monthly_income > inflated_monthly_income:
                    excess_income = guaranteed_monthly_income - inflated_monthly_income
                    isa_allowance_rem = max(0.0, self.ISA_ANNUAL_ALLOWANCE - isa_credited_this_tax_year)
                    
                    to_isa = min(excess_income, isa_allowance_rem)
                    to_other = excess_income - to_isa

                    isa += to_isa
                    other += to_other
                    isa_credited_this_tax_year += to_isa
                    needed_net = 0.0
                else:
                    needed_net = inflated_monthly_income - guaranteed_monthly_income

                if in_crash_window:
                    if needed_net > 0 and other > 0:
                        draw = min(other, needed_net)
                        other -= draw
                        needed_net -= draw
                        monthly_drawn_from_pots += draw
                else:
                    allowance_rem = max(
                        0.0, self.PERSONAL_ALLOWANCE - taxable_income_this_tax_year
                    )
                    if allowance_rem > 0 and needed_net > 0:
                        target = min(needed_net, allowance_rem)
                        tot_taxable = sipp + wp_taxable
                        draw = min(tot_taxable, target)

                        if draw > 0:
                            s_share = sipp / tot_taxable
                            wp_share = wp_taxable / tot_taxable
                            sipp -= draw * s_share
                            wp_taxable -= draw * wp_share
                            taxable_income_this_tax_year += draw
                            needed_net -= draw
                            monthly_drawn_from_pots += draw

                    if needed_net > 0 and isa > 0:
                        draw = min(isa, needed_net)
                        isa -= draw
                        needed_net -= draw
                        monthly_drawn_from_pots += draw

                    if needed_net > 0 and wp_tax_free > 0:
                        draw = min(wp_tax_free, needed_net)
                        wp_tax_free -= draw
                        needed_net -= draw
                        monthly_drawn_from_pots += draw

                    tot_taxable = sipp + wp_taxable
                    if needed_net > 0 and tot_taxable > 0:
                        gross_needed = needed_net / (1.0 - self.BASIC_TAX_RATE)
                        gross_draw = min(tot_taxable, gross_needed)

                        if gross_draw > 0:
                            s_share = sipp / tot_taxable
                            wp_share = wp_taxable / tot_taxable
                            sipp -= gross_draw * s_share
                            wp_taxable -= gross_draw * wp_share

                            net_rec = gross_draw * (1.0 - self.BASIC_TAX_RATE)
                            tax = gross_draw * self.BASIC_TAX_RATE

                            taxable_income_this_tax_year += gross_draw
                            needed_net -= net_rec
                            monthly_drawn_from_pots += net_rec
                            tax_paid += tax

                    if needed_net > 0 and other > 0:
                        draw = min(other, needed_net)
                        other -= draw
                        needed_net -= draw
                        monthly_drawn_from_pots += draw

                # Track unfulfilled shortfall as negative portfolio deficit
                if needed_net > 0:
                    cumulative_deficit += needed_net

            # Strictly Defined Contribution pot balance for Private Pension (annuity excluded)
            private_pension_val = wp_taxable + wp_tax_free
            total_portfolio = (sipp + wp_taxable + wp_tax_free + isa + other) - cumulative_deficit
            total_monthly_income = monthly_drawn_from_pots + state_pension_monthly + annuity_monthly

            daily_records.append({
                "date": current_date,
                "tax_year": current_tax_year,
                "raw_month": current_date.strftime("%Y-%m"),
                "age": age,
                "is_retired": is_retired,
                "desired_monthly_income": int(round(inflated_monthly_income)),
                "desired_annual_income": int(round(inflated_monthly_income * 12.0)),
                "sipp": int(round(sipp)),
                "private_pension": int(round(private_pension_val)),
                "workplace_tax_free": int(round(wp_tax_free)),
                "workplace_taxable": int(round(wp_taxable)),
                "isa": int(round(isa)),
                "other_investment": int(round(other)),
                "total_portfolio": int(round(total_portfolio)),
                "annuity_income": int(round(current_annual_annuity if is_retired else 0.0)),
                "state_pension_income": int(round(state_pension_monthly)),
                "pot_income_drawn": int(round(monthly_drawn_from_pots)),
                "monthly_net_income": int(round(total_monthly_income)),
                "tax_paid": int(round(tax_paid)),
            })

            current_date += timedelta(days=1)

        df = pd.DataFrame(daily_records)

        # Monthly Snapshot Aggregation (grouped strictly by unique YYYY-MM)
        monthly_df = (
            df.groupby("raw_month")
            .agg({
                "date": "last",
                "age": "last",
                "is_retired": "last",
                "desired_monthly_income": "last",
                "desired_annual_income": "last",
                "sipp": "last",
                "private_pension": "last",
                "isa": "last",
                "other_investment": "last",
                "total_portfolio": "last",
                "annuity_income": "last",
                "state_pension_income": "sum",
                "pot_income_drawn": "sum",
                "monthly_net_income": "sum",
                "tax_paid": "sum",
            })
            .reset_index()
        )
        monthly_df["year_month"] = monthly_df.apply(lambda r: f"{r['raw_month']} ({r['age']})", axis=1)

        # Tax Year Snapshot Aggregation (grouped strictly by unique tax_year)
        tax_year_df = (
            df.groupby("tax_year")
            .agg({
                "date": "last",
                "age": "last",
                "is_retired": "last",
                "desired_monthly_income": "last",
                "desired_annual_income": "last",
                "sipp": "last",
                "private_pension": "last",
                "isa": "last",
                "other_investment": "last",
                "total_portfolio": "last",
                "annuity_income": "last",
                "state_pension_income": "sum",
                "pot_income_drawn": "sum",
                "monthly_net_income": "sum",
                "tax_paid": "sum",
            })
            .reset_index()
        )
        tax_year_df["tax_year_with_age"] = tax_year_df.apply(lambda r: f"{r['tax_year']} ({r['age']})", axis=1)
        tax_year_df["monthly_net_income"] = (tax_year_df["monthly_net_income"] / 12.0).round(0)

        num_cols = [
            "desired_monthly_income",
            "desired_annual_income",
            "sipp",
            "private_pension",
            "isa",
            "other_investment",
            "total_portfolio",
            "annuity_income",
            "state_pension_income",
            "pot_income_drawn",
            "monthly_net_income",
            "tax_paid",
        ]
        monthly_df[num_cols] = monthly_df[num_cols].round(0).astype(int)
        tax_year_df[num_cols] = tax_year_df[num_cols].round(0).astype(int)

        return monthly_df, tax_year_df


# ----------------------------------------------------------------------
# 4. Streamlit Sidebar: Profile Management & Inputs Form
# ----------------------------------------------------------------------

st.sidebar.header("📁 Profile & Scenario Manager")

scenario_list = list(st.session_state.scenarios.keys())
if st.session_state.active_scenario_name not in scenario_list:
    st.session_state.active_scenario_name = scenario_list[0]

selected_profile = st.sidebar.selectbox(
    "Select Active Profile:",
    options=scenario_list,
    index=scenario_list.index(st.session_state.active_scenario_name),
)

st.session_state.active_scenario_name = selected_profile

with st.sidebar.expander("➕ Add New Profile / Copy Current"):
    new_profile_name = st.text_input("New Profile Name:", placeholder="e.g. Early Retirement")
    if st.button("Create Profile"):
        if new_profile_name and new_profile_name not in st.session_state.scenarios:
            st.session_state.scenarios[new_profile_name] = st.session_state.scenarios[selected_profile].copy()
            st.session_state.active_scenario_name = new_profile_name
            save_scenarios()
            st.success(f"Profile '{new_profile_name}' created and saved!")
            st.rerun()
        elif new_profile_name in st.session_state.scenarios:
            st.warning("Profile name already exists.")

# Delete Non-Default Profile Feature
if selected_profile not in DEFAULT_PROFILES:
    if st.sidebar.button(f"🗑️ Delete Profile '{selected_profile}'", use_container_width=True):
        del st.session_state.scenarios[selected_profile]
        save_scenarios()
        st.session_state.active_scenario_name = list(st.session_state.scenarios.keys())[0]
        st.toast(f"Deleted profile '{selected_profile}'", icon="🗑️")
        st.rerun()
else:
    st.sidebar.caption("🔒 Default profile (cannot be deleted)")

curr_data = st.session_state.scenarios[selected_profile]

st.sidebar.markdown("---")

with st.sidebar.form(key=f"scenario_form_{selected_profile}"):
    st.header(f"⚙️ Edit '{selected_profile}'")

    submit_top = st.form_submit_button(
        label="🔄 Recalculate Forecast", use_container_width=True, key="recalc_top"
    )

    with st.expander("👤 Core Profile & Income Goals", expanded=True):
        dob = st.date_input(
            "Date of Birth",
            value=curr_data["dob"],
            min_value=date(1920, 1, 1),
            max_value=date.today(),
            format="DD/MM/YYYY",
        )
        ret_age = st.number_input(
            "Target Retirement Age", min_value=50, max_value=85, value=int(curr_data["ret_age"])
        )
        monthly_inc = st.number_input(
            "Desired Monthly Income (£)",
            min_value=100.0,
            value=float(curr_data["monthly_inc"]),
            step=100.0,
        )
        increased_monthly_inc = st.number_input(
            "Increase Income To (£)",
            min_value=0.0,
            value=float(curr_data.get("increased_monthly_inc", 0.0)),
            step=100.0,
            help="Set above £0 to step up monthly income from Increase Date onwards.",
        )
        increase_date = st.date_input(
            "Increase Date",
            value=curr_data.get("increase_date", get_next_tax_year_start()),
            min_value=date.today(),
            format="DD/MM/YYYY",
        )
        default_reduced_inc = curr_data.get("reduced_monthly_inc", curr_data["monthly_inc"])
        reduced_monthly_inc = st.number_input(
            "Reduce Income To (£)",
            min_value=0.0,
            value=float(default_reduced_inc),
            step=50.0,
            help="Defaults to matching Desired Monthly Income unless explicitly changed.",
        )
        reduced_inc_age = st.number_input(
            "Reduced Income Age",
            min_value=50,
            max_value=100,
            value=int(curr_data.get("reduced_inc_age", 80)),
        )
        inflation_rate = st.slider(
            "Annual Inflation Rate (%)",
            min_value=0.0,
            max_value=10.0,
            value=float(curr_data.get("inflation_rate", 3.0)),
            step=0.1,
        )

    with st.expander("💵 Lump Sum Injections / Withdrawals (Up to 3)", expanded=False):
        pot_options = ["S&S ISA", "SIPP", "Private Pension", "Other Investment"]

        st.markdown("##### Lump Sum 1")
        ls1_amt = st.number_input("Lump Sum 1 Amount (£)", min_value=-1000000.0, value=float(curr_data.get("lump_sum_1_amt", 0.0)), step=1000.0, help="Enter a negative amount to simulate a withdrawal.")
        ls1_date = st.date_input("Lump Sum 1 Date", value=curr_data.get("lump_sum_1_date", get_next_tax_year_start()), min_value=date.today(), format="DD/MM/YYYY")
        ls1_pot = st.selectbox("Lump Sum 1 Target Pot", options=pot_options, index=pot_options.index("Private Pension" if curr_data.get("lump_sum_1_pot") == "Workplace Pension" else curr_data.get("lump_sum_1_pot", "S&S ISA")))

        st.markdown("##### Lump Sum 2")
        ls2_amt = st.number_input("Lump Sum 2 Amount (£)", min_value=-1000000.0, value=float(curr_data.get("lump_sum_2_amt", 0.0)), step=1000.0, help="Enter a negative amount to simulate a withdrawal.")
        ls2_date = st.date_input("Lump Sum 2 Date", value=curr_data.get("lump_sum_2_date", get_next_tax_year_start()), min_value=date.today(), format="DD/MM/YYYY")
        ls2_pot = st.selectbox("Lump Sum 2 Target Pot", options=pot_options, index=pot_options.index("Private Pension" if curr_data.get("lump_sum_2_pot") == "Workplace Pension" else curr_data.get("lump_sum_2_pot", "S&S ISA")))

        st.markdown("##### Lump Sum 3")
        ls3_amt = st.number_input("Lump Sum 3 Amount (£)", min_value=-1000000.0, value=float(curr_data.get("lump_sum_3_amt", 0.0)), step=1000.0, help="Enter a negative amount to simulate a withdrawal.")
        ls3_date = st.date_input("Lump Sum 3 Date", value=curr_data.get("lump_sum_3_date", get_next_tax_year_start()), min_value=date.today(), format="DD/MM/YYYY")
        ls3_pot = st.selectbox("Lump Sum 3 Target Pot", options=pot_options, index=pot_options.index("Private Pension" if curr_data.get("lump_sum_3_pot") == "Workplace Pension" else curr_data.get("lump_sum_3_pot", "S&S ISA")))

    try:
        max_crash_date = date(dob.year + 100, dob.month, dob.day)
    except ValueError:
        max_crash_date = date(dob.year + 100, 2, 28)

    with st.expander("📉 Market Stress Testing", expanded=False):
        crash_pct = st.slider(
            "Market Crash (%)",
            min_value=0.0,
            max_value=75.0,
            value=float(curr_data.get("crash_pct", 0.0)),
            step=1.0,
        )
        crash_date = st.date_input(
            "Crash Date",
            value=curr_data.get("crash_date", get_next_tax_year_start()),
            min_value=date.today(),
            max_value=max_crash_date,
            format="DD/MM/YYYY",
        )

    with st.expander("📜 Pension Annuity / Defined Benefit", expanded=False):
        annuity_annual = st.number_input("Annual Pension / Annuity (£)", min_value=0.0, value=float(curr_data.get("annuity_annual", 0.0)), step=500.0)
        annuity_cost = st.number_input("Cost of Annuity (£)", min_value=0.0, value=float(curr_data.get("annuity_cost", 0.0)), step=5000.0, help="Leave at £0 for Defined Benefit / Final Salary pensions.")
        annuity_start_age = st.number_input(
            "Annuity / DB Pension Start Age",
            min_value=50,
            max_value=85,
            value=int(curr_data.get("annuity_start_age", 65)),
            step=1,
            help="Set the age at which pension annuity / Defined Benefit income payments begin.",
        )
        inflate_annuity_to_start = st.checkbox(
            "Inflate Pension/Annuity to Start Age",
            value=curr_data.get("inflate_annuity_to_start", False),
            help="Check this if the entered annual figure is in today's money. It will grow by inflation until the start age before payments begin.",
        )

    with st.expander("🏛️ State Pension", expanded=False):
        has_state_pension = st.checkbox("Include State Pension", value=curr_data.get("has_state_pension", True))
        state_pension_age = st.number_input("State Pension Start Age", min_value=60, max_value=75, value=int(curr_data.get("state_pension_age", 67)))
        state_pension_amount = st.number_input("State Pension Annual (£)", min_value=0.0, value=float(curr_data.get("state_pension_amount", 12548.0)), step=100.0)
        state_pension_growth = st.slider("State Pension Annual Growth (%)", min_value=0.0, max_value=10.0, value=float(curr_data.get("state_pension_growth", 2.5)), step=0.1)

    with st.expander("💰 Pot Balances, Returns & Contributions", expanded=False):
        st.markdown("##### SIPP")
        sipp_bal = st.number_input("SIPP Pot Balance (£)", value=float(curr_data["sipp_bal"]), step=5000.0)
        sipp_ret = st.slider("SIPP Annual Return (%)", 0.0, 15.0, float(curr_data.get("sipp_ret", 7.0)))
        sipp_contrib = st.number_input("SIPP Monthly Contribution (£)", value=float(curr_data.get("sipp_contrib", 500.0)), step=50.0)

        st.markdown("##### Private Pension")
        wp_bal = st.number_input("Private Pension Total (£)", value=float(curr_data["wp_bal"]), step=5000.0)
        wp_ret = st.slider("Private Pension Return (%)", 0.0, 15.0, float(curr_data.get("wp_ret", 7.0)))
        wp_contrib = st.number_input("Private Pension Monthly Contribution (£)", value=float(curr_data.get("wp_contrib", 700.0)), step=50.0)

        st.markdown("##### Stocks & Shares ISA")
        isa_bal = st.number_input("Stocks & Shares ISA (£)", value=float(curr_data["isa_bal"]), step=5000.0)
        isa_ret = st.slider("ISA Annual Return (%)", 0.0, 15.0, float(curr_data.get("isa_ret", 7.0)))
        isa_contrib = st.number_input("ISA Monthly Contribution (£)", value=float(curr_data.get("isa_contrib", 0.0)), step=50.0)

        st.markdown("##### Other Investment")
        other_bal = st.number_input("Other Investment (£)", value=float(curr_data["other_bal"]), step=5000.0)
        other_ret = st.slider("Other Return (%)", 0.0, 15.0, float(curr_data.get("other_ret", 3.0)))
        other_contrib = st.number_input("Other Monthly Contribution (£)", value=float(curr_data.get("other_contrib", 0.0)), step=50.0)

    with st.expander("👁️ Display View", expanded=False):
        view_mode = st.radio(
            "Display View Mode",
            ["Tax Year", "Monthly (Default)"],
            index=0 if curr_data["view_mode"] == "Tax Year" else 1,
        )

    submit_bottom = st.form_submit_button(
        label="🔄 Recalculate Forecast", use_container_width=True, key="recalc_bottom"
    )

    if submit_top or submit_bottom:
        st.session_state.scenarios[selected_profile] = {
            "dob": dob,
            "ret_age": ret_age,
            "monthly_inc": monthly_inc,
            "increased_monthly_inc": increased_monthly_inc,
            "increase_date": increase_date,
            "reduced_monthly_inc": reduced_monthly_inc,
            "reduced_inc_age": reduced_inc_age,
            "inflation_rate": inflation_rate,
            "lump_sum_1_amt": ls1_amt,
            "lump_sum_1_date": ls1_date,
            "lump_sum_1_pot": ls1_pot,
            "lump_sum_2_amt": ls2_amt,
            "lump_sum_2_date": ls2_date,
            "lump_sum_2_pot": ls2_pot,
            "lump_sum_3_amt": ls3_amt,
            "lump_sum_3_date": ls3_date,
            "lump_sum_3_pot": ls3_pot,
            "crash_pct": crash_pct,
            "crash_date": crash_date,
            "annuity_annual": annuity_annual,
            "annuity_cost": annuity_cost,
            "annuity_start_age": annuity_start_age,
            "inflate_annuity_to_start": inflate_annuity_to_start,
            "sipp_bal": sipp_bal,
            "sipp_ret": sipp_ret,
            "sipp_contrib": sipp_contrib,
            "wp_bal": wp_bal,
            "wp_ret": wp_ret,
            "wp_contrib": wp_contrib,
            "isa_bal": isa_bal,
            "isa_ret": isa_ret,
            "isa_contrib": isa_contrib,
            "other_bal": other_bal,
            "other_ret": other_ret,
            "other_contrib": other_contrib,
            "has_state_pension": has_state_pension,
            "state_pension_age": state_pension_age,
            "state_pension_amount": state_pension_amount,
            "state_pension_growth": state_pension_growth,
            "view_mode": view_mode,
            "notes": curr_data.get("notes", ""),
            "budget_items": curr_data.get("budget_items", []),
        }
        save_scenarios()
        st.toast(f"Updated and saved '{selected_profile}'!", icon="✅")
        st.rerun()


# ----------------------------------------------------------------------
# 5. Main Dashboard Display
# ----------------------------------------------------------------------

active_p = st.session_state.scenarios[selected_profile]

lump_sums_list = [
    LumpSum(
        amount=active_p.get("lump_sum_1_amt", 0.0),
        injection_date=active_p.get("lump_sum_1_date", get_next_tax_year_start()),
        target_pot="Private Pension" if active_p.get("lump_sum_1_pot") == "Workplace Pension" else active_p.get("lump_sum_1_pot", "S&S ISA"),
    ),
    LumpSum(
        amount=active_p.get("lump_sum_2_amt", 0.0),
        injection_date=active_p.get("lump_sum_2_date", get_next_tax_year_start()),
        target_pot="Private Pension" if active_p.get("lump_sum_2_pot") == "Workplace Pension" else active_p.get("lump_sum_2_pot", "S&S ISA"),
    ),
    LumpSum(
        amount=active_p.get("lump_sum_3_amt", 0.0),
        injection_date=active_p.get("lump_sum_3_date", get_next_tax_year_start()),
        target_pot="Private Pension" if active_p.get("lump_sum_3_pot") == "Workplace Pension" else active_p.get("lump_sum_3_pot", "S&S ISA"),
    ),
]

scenario_obj = Scenario(
    name=selected_profile,
    sipp=PotConfig(
        balance=active_p["sipp_bal"],
        annual_return=active_p["sipp_ret"] / 100.0,
        monthly_contrib=active_p.get("sipp_contrib", 500.0),
    ),
    workplace_pension_total=active_p["wp_bal"],
    workplace_pension_return=active_p["wp_ret"] / 100.0,
    workplace_pension_contrib=active_p.get("wp_contrib", 700.0),
    isa=PotConfig(
        balance=active_p["isa_bal"],
        annual_return=active_p["isa_ret"] / 100.0,
        monthly_contrib=active_p.get("isa_contrib", 0.0),
    ),
    other_investment=PotConfig(
        balance=active_p["other_bal"],
        annual_return=active_p["other_ret"] / 100.0,
        monthly_contrib=active_p.get("other_contrib", 0.0),
    ),
    has_state_pension=active_p.get("has_state_pension", True),
    state_pension_age=active_p.get("state_pension_age", 67),
    state_pension_amount=active_p.get("state_pension_amount", 12548.0),
    lump_sums=lump_sums_list,
    state_pension_growth=active_p.get("state_pension_growth", 2.5) / 100.0,
    inflation_rate=active_p.get("inflation_rate", 3.0) / 100.0,
    annuity_annual=active_p.get("annuity_annual", 0.0),
    annuity_cost=active_p.get("annuity_cost", 0.0),
    annuity_start_age=int(active_p.get("annuity_start_age", 65)),
    inflate_annuity_to_start=active_p.get("inflate_annuity_to_start", False),
    increased_monthly_inc=active_p.get("increased_monthly_inc", 0.0),
    increase_date=active_p.get("increase_date", get_next_tax_year_start()),
    reduced_monthly_inc=active_p.get("reduced_monthly_inc", active_p["monthly_inc"]),
    reduced_inc_age=int(active_p.get("reduced_inc_age", 80)),
    crash_pct=active_p.get("crash_pct", 0.0),
    crash_date=active_p.get("crash_date", get_next_tax_year_start()),
)

engine = RetirementEngine(
    dob=active_p["dob"],
    retirement_age=int(active_p["ret_age"]),
    monthly_income=active_p["monthly_inc"],
    scenario=scenario_obj,
)

m_df, ty_df = engine.run_simulation()

active_df = ty_df if active_p["view_mode"] == "Tax Year" else m_df
x_col = "tax_year_with_age" if active_p["view_mode"] == "Tax Year" else "year_month"
annual_inc = int(round(active_p["monthly_inc"] * 12.0))

today = date.today()
current_age = (
    today.year
    - active_p["dob"].year
    - ((today.month, today.day) < (active_p["dob"].month, active_p["dob"].day))
)

retired_df = active_df[active_df["is_retired"]]
depleted_rows = retired_df[retired_df["total_portfolio"] <= 0]

if not depleted_rows.empty:
    depleted_val_str = f"Age {int(depleted_rows.iloc[0]['age'])}"
else:
    final_bal = int(round(active_df.iloc[-1]["total_portfolio"]))
    depleted_val_str = f"£{final_bal:,}"

st.subheader(f"Showing Profile: **{selected_profile}**")

st.markdown(
    """
    <style>
    [data-testid="stMetricValue"] {
        font-size: 1.2rem !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Current Age", f"{current_age}")
col2.metric("Target Retirement Age", f"{int(active_p['ret_age'])}")
col3.metric("Peak Portfolio Value", f"£{int(round(active_df['total_portfolio'].max())):,}")
col4.metric("Desired Monthly Income", f"£{int(round(active_p['monthly_inc'])):,}")
col5.metric("Desired Annual Income", f"£{annual_inc:,}")
col6.metric("Portfolio Depleted / Age 100", depleted_val_str)

st.markdown("---")

st.subheader("📊 Portfolio Trajectory & Drawdown Forecast")
st.line_chart(
    active_df,
    x=x_col,
    y=["sipp", "private_pension", "isa", "other_investment", "total_portfolio", "desired_annual_income"],
)

st.subheader("📋 Balances and Drawdown Table (Up to Age 100)")

table_column_config = {
    "desired_monthly_income": st.column_config.NumberColumn("Desired Monthly Income", format="£%,d"),
    "desired_annual_income": st.column_config.NumberColumn("Desired Annual Income", format="£%,d"),
    "sipp": st.column_config.NumberColumn("SIPP", format="£%,d"),
    "private_pension": st.column_config.NumberColumn("Private Pension", format="£%,d"),
    "isa": st.column_config.NumberColumn("S&S ISA", format="£%,d"),
    "other_investment": st.column_config.NumberColumn("Other Investment", format="£%,d"),
    "total_portfolio": st.column_config.NumberColumn("Total Portfolio", format="£%,d"),
    "annuity_income": st.column_config.NumberColumn("Annuity Income (Annual)", format="£%,d"),
    "state_pension_income": st.column_config.NumberColumn("State Pension Income", format="£%,d"),
    "pot_income_drawn": st.column_config.NumberColumn("Pot Income Drawn", format="£%,d"),
    "monthly_net_income": st.column_config.NumberColumn("Monthly Net Income", format="£%,d"),
    "tax_paid": st.column_config.NumberColumn("Tax Paid", format="£%,d"),
}

st.dataframe(active_df, column_config=table_column_config, height=670, use_container_width=True)

st.markdown("---")

# ----------------------------------------------------------------------
# 6. Budget Manager & Custom Notes Sections
# ----------------------------------------------------------------------

col_sec1, col_sec2 = st.columns(2)

with col_sec1:
    with st.expander("💳 Household Budget Manager", expanded=False):
        st.markdown(f"### Monthly Budget for **{selected_profile}**")
        st.caption("Align your household outgoings against your desired monthly income target.")

        budget_items = active_p.get("budget_items", [])
        total_budget_outgoings = sum(item.get("amount", 0.0) for item in budget_items)
        desired_inc = float(active_p["monthly_inc"])
        budget_variance = desired_inc - total_budget_outgoings

        bcol1, bcol2, bcol3 = st.columns(3)
        bcol1.metric("Total Outgoings", f"£{total_budget_outgoings:,.2f}")
        bcol2.metric("Desired Income", f"£{desired_inc:,.2f}")
        bcol3.metric("Monthly Buffer / Surplus", f"£{budget_variance:,.2f}", delta=f"£{budget_variance:,.2f}")

        st.markdown("---")
        st.markdown("#### Edit Budget Line Items")

        updated_budget_items = []
        for i, item in enumerate(budget_items):
            cols = st.columns([3, 2, 1])
            with cols[0]:
                cat_val = st.text_input("Category", value=item.get("category", ""), key=f"budget_cat_{selected_profile}_{i}")
            with cols[1]:
                amt_val = st.number_input("Amount (£)", value=float(item.get("amount", 0.0)), step=25.0, key=f"budget_amt_{selected_profile}_{i}")
            with cols[2]:
                st.markdown("<br>", unsafe_allow_html=True)
                remove_clicked = st.button("🗑️", key=f"del_budget_{selected_profile}_{i}")
            
            if not remove_clicked:
                updated_budget_items.append({"category": cat_val, "amount": amt_val})

        st.markdown("##### Add New Budget Item")
        new_cat = st.text_input("New Category Name", placeholder="e.g. Insurance, Gym...", key=f"new_cat_{selected_profile}")
        new_amt = st.number_input("New Amount (£)", min_value=0.0, value=0.0, step=25.0, key=f"new_amt_{selected_profile}")

        if st.button("➕ Add Item to Budget", key=f"add_budget_btn_{selected_profile}"):
            if new_cat:
                updated_budget_items.append({"category": new_cat, "amount": new_amt})
                st.session_state.scenarios[selected_profile]["budget_items"] = updated_budget_items
                save_scenarios()
                st.success("Item added!")
                st.rerun()
            else:
                st.warning("Please enter a category name.")

        if st.button("💾 Save Budget Changes", key=f"save_budget_btn_{selected_profile}"):
            st.session_state.scenarios[selected_profile]["budget_items"] = updated_budget_items
            save_scenarios()
            st.toast(f"Budget saved for profile '{selected_profile}'!", icon="💾")
            st.rerun()

with col_sec2:
    with st.expander("📝 Custom Profile Notes", expanded=False):
        notes_key = f"notes_input_{selected_profile}"
        user_notes = st.text_area(
            "Notes & Key Assumptions for this Profile:",
            value=active_p.get("notes", ""),
            height=180,
            key=notes_key,
            placeholder="Type any custom notes, reminders, or scenario assumptions here...",
        )
        
        if st.button("💾 Save Notes", key=f"save_notes_btn_{selected_profile}"):
            st.session_state.scenarios[selected_profile]["notes"] = user_notes
            save_scenarios()
            st.toast(f"Notes saved for profile '{selected_profile}'!", icon="💾")

st.markdown("---")

col_notes1, col_notes2 = st.columns(2)

with col_notes1:
    with st.expander("📖 Drawdown Priorities & Engine Logic Notes"):
        st.markdown("""
        ### Post-Retirement Drawdown Priorities & Rules

        This engine applies strict, tax-efficient drawdown rules in a defined sequence on the 1st of every month:

        1. **Guaranteed Income First (Annuity & State Pension):**
           * **Annuities / DB Pension:** Annual pension annuity payments are applied first and increase with inflation after Year 1.
           * **State Pension:** Applied automatically once you reach your configured State Pension age, escalating annually by your growth input.
           * **Excess Income Recycling:** If guaranteed income exceeds your target inflation-adjusted monthly income, the surplus is automatically deposited into your **S&S ISA** (up to the **£20,000/year** limit), with any remaining excess directed to **Other Investments**.

        2. **Market Stress Buffer Strategy (> 5% Crash Trigger):**
           * If a market crash of **> 5%** occurs (configurable at any age up to 100), the engine enters a **2-year recovery window**.
           * During recovery, equity pots (**SIPP**, **Private Pension**, **ISA**) are protected from panic sell-offs.
           * **Income Reduction Rule:** Your target monthly income is automatically reduced to match the **State Pension amount** calculated at the date of the crash.
           * **Post-Recovery:** After the 2-year window expires, your desired monthly income resumes at its full inflation-adjusted level.

        3. **Standard Tax-Optimized Drawdown Hierarchy:**
           When guaranteed income is insufficient, the required shortfall is satisfied using the following priority order:
           * **Priority 1 (Personal Allowance Utilization):** Draws taxable pensions (**SIPP** and **75% Private Pension**) up to the remaining UK Personal Allowance threshold (**£12,570/year**) to receive income **100% tax-free**.
           * **Priority 2 (Tax-Free ISA Capital):** Draws from **S&S ISA** to fulfill remaining income needs without incurring income tax.
           * **Priority 3 (Tax-Free Pension Capital):** Draws from the tax-free portion (**25% Private Pension**).
           * **Priority 4 (Basic Rate Taxable Pensions):** Draws taxable pensions above the Personal Allowance, applying basic-rate income tax (**20%**) to calculate gross withdrawals.
           * **Priority 5 (Other Investments Fallback):** Draws remaining needs from non-registered/taxable investments.
        """)

with col_notes2:
    with st.expander("📚 Historical Market Crash & Recovery Reference Data"):
        st.markdown("""
        ### Top 10 Global Market Crashes & Recovery Timelines
        
        | # | Event & Timeline | S&P 500 Decline (%) | S&P 500 Recovery Time | FTSE 100 Decline (%) | FTSE 100 Recovery Time | Primary Driver |
        |---|---|---|---|---|---|---|
        | **1** | **Wall Street Crash** *(1929–1932)* | **-86.2%** | **~25.2 years** *(Nov 1954)* | **N/A** *(FT Ord: ~24 yrs)* | **N/A** | Speculative equity bubble, margin leverage, banking panics |
        | **2** | **OPEC Oil Shock** *(1973–1974)* | **-48.2%** | **~7.5 years** *(Jul 1980)* | **N/A** *(FT Ord: ~3.5 yrs)* | **N/A** | Arab oil embargo, high inflation, Bretton Woods collapse |
        | **3** | **Black Monday** *(1987)* | **-33.5%** | **~1.8 years** *(Jul 1989)* | **-36.8%** | **~2.1 years** *(Nov 1989)* | Automated program trading, valuation concerns |
        | **4** | **Gulf War Crash** *(1990)* | **-19.9%** | **~6 months** *(Feb 1991)* | **-21.8%** | **~7 months** *(Feb 1991)* | Iraqi invasion of Kuwait, oil price spike, US recession |
        | **5** | **Russian Debt & LTCM** *(1998)* | **-19.3%** | **~3 months** *(Nov 1998)* | **-21.7%** | **~6 months** *(Feb 1999)* | Russian sovereign debt default, LTCM hedge fund collapse |
        | **6** | **Dot-Com Bubble Burst** *(2000–2003)* | **-49.1%** | **~7.2 years** *(May 2007)* | **-52.6%** | **~7.8 years** *(Nov 2007)* | Tech overvaluation, corporate accounting scandals |
        | **7** | **Global Financial Crisis** *(2007–2009)* | **-56.8%** | **~5.5 years** *(Mar 2013)* | **-48.3%** | **~7.3 years** *(Feb 2015)* | Subprime mortgage collapse, Lehman Brothers collapse |
        | **8** | **European Debt Crisis** *(2011)* | **-19.4%** | **~6 months** *(Feb 2012)* | **-20.2%** | **~1.5 years** *(Feb 2013)* | Eurozone debt fears (Greece/Italy), US credit downgrade |
        | **9** | **COVID-19 Pandemic** *(2020)* | **-33.9%** | **~5 months** *(Aug 2020)* | **-34.8%** | **~2.8 years** *(Jan 2023)* | Global lockdowns, economic shutdown, pandemic uncertainty |
        | **10** | **Inflation & Rate Hikes** *(2022)* | **-25.4%** | **~2.2 years** *(Jan 2024)* | **-10.3%** | **~4 months** *(Feb 2023)* | Post-pandemic inflation spike, aggressive rate hikes |
        
        *Note: The FTSE 100 was introduced on January 3, 1984. Recovery times reflect nominal market price returns reaching previous peaks.*
        """)
