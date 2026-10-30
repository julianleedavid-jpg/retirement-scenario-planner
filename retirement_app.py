from dataclasses import dataclass, field
from datetime import date, timedelta
import json
import os
import calendar
from typing import List, Tuple
import uuid
import base64
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
st.set_page_config(page_title="Retirement Scenario Planner", layout="wide")


# ----------------------------------------------------------------------
# 0. Password Protection Gate (Placed at top before any UI renders)
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
# 1. Google Sheets Persistence & Default Scenarios
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
        "annuity_npa": 65,
        "annuity_type": "Inflation-Linked (RPI/CPI)",
        "inflate_annuity_to_start": False,
        "apply_db_early_reduction": True,
        "has_nuvos_pension": False,
        "nuvos_annual": 15929.31,
        "nuvos_baseline_date": date(2025, 3, 31),
        "nuvos_npa": 65,
        "nuvos_pause_enabled": True,
        "nuvos_pause_date": get_next_tax_year_start(),
        "nuvos_salary": 57015.0,
        "nuvos_accrual_rate": 2.3,
        "apply_nuvos_early_reduction": True,
        "lump_sum_1_amt": 0.0,
        "lump_sum_1_date": get_next_tax_year_start(),
        "lump_sum_1_pot": "S&S ISA",
        "lump_sum_2_amt": 0.0,
        "lump_sum_2_date": get_next_tax_year_start(),
        "lump_sum_2_pot": "S&S ISA",
        "lump_sum_3_amt": 0.0,
        "lump_sum_3_date": get_next_tax_year_start(),
        "lump_sum_3_pot": "S&S ISA",
        "gilt_1_amt": 0.0,
        "gilt_1_price": 100.0,
        "gilt_1_p_date": get_next_tax_year_start(),
        "gilt_1_m_date": get_next_tax_year_start(),
        "gilt_1_pot": "S&S ISA",
        "gilt_1_coupon_pct": 0.0,
        "gilt_2_amt": 0.0,
        "gilt_2_price": 100.0,
        "gilt_2_p_date": get_next_tax_year_start(),
        "gilt_2_m_date": get_next_tax_year_start(),
        "gilt_2_pot": "S&S ISA",
        "gilt_2_coupon_pct": 0.0,
        "gilt_3_amt": 0.0,
        "gilt_3_price": 100.0,
        "gilt_3_p_date": get_next_tax_year_start(),
        "gilt_3_m_date": get_next_tax_year_start(),
        "gilt_3_pot": "S&S ISA",
        "gilt_3_coupon_pct": 0.0,
        "gilt_4_amt": 0.0,
        "gilt_4_price": 100.0,
        "gilt_4_p_date": get_next_tax_year_start(),
        "gilt_4_m_date": get_next_tax_year_start(),
        "gilt_4_pot": "S&S ISA",
        "gilt_4_coupon_pct": 0.0,
        "gilt_5_amt": 0.0,
        "gilt_5_price": 100.0,
        "gilt_5_p_date": get_next_tax_year_start(),
        "gilt_5_m_date": get_next_tax_year_start(),
        "gilt_5_pot": "S&S ISA",
        "gilt_5_coupon_pct": 0.0,
        "crash_pct": 0.0,
        "crash_date": get_next_tax_year_start(),
        "view_mode": "Age Year (Annual)",
        "notes": "",
        "budget_items": [
            {"id": str(uuid.uuid4()), "item": "Housing / Council Tax", "amount": 800.0, "month_paid": "Monthly", "annual_amount": 9600.0},
            {"id": str(uuid.uuid4()), "item": "Utilities & Broadband", "amount": 250.0, "month_paid": "Monthly", "annual_amount": 3000.0},
            {"id": str(uuid.uuid4()), "item": "Groceries", "amount": 400.0, "month_paid": "Monthly", "annual_amount": 4800.0},
            {"id": str(uuid.uuid4()), "item": "Transport & Fuel", "amount": 200.0, "month_paid": "Monthly", "annual_amount": 2400.0},
            {"id": str(uuid.uuid4()), "item": "Leisure & Holidays", "amount": 350.0, "month_paid": "Monthly", "annual_amount": 4200.0},
        ],
    },
    "Karen": {
        "dob": date(1980, 10, 16),
        "ret_age": 57,
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
        "annuity_annual": 2989.38,
        "annuity_cost": 0.0,
        "annuity_start_age": 57,
        "annuity_npa": 65,
        "annuity_type": "Inflation-Linked (RPI/CPI)",
        "inflate_annuity_to_start": True,
        "apply_db_early_reduction": True,
        "has_nuvos_pension": True,
        "nuvos_annual": 15929.31,
        "nuvos_baseline_date": date(2025, 3, 31),
        "nuvos_npa": 65,
        "nuvos_pause_enabled": True,
        "nuvos_pause_date": date(2037, 10, 16),
        "nuvos_salary": 57015.0,
        "nuvos_accrual_rate": 2.3,
        "apply_nuvos_early_reduction": True,
        "lump_sum_1_amt": 6214.78,
        "lump_sum_1_date": date(2037, 10, 16),
        "lump_sum_1_pot": "S&S ISA",
        "lump_sum_2_amt": 0.0,
        "lump_sum_2_date": get_next_tax_year_start(),
        "lump_sum_2_pot": "S&S ISA",
        "lump_sum_3_amt": 0.0,
        "lump_sum_3_date": get_next_tax_year_start(),
        "lump_sum_3_pot": "S&S ISA",
        "gilt_1_amt": 0.0,
        "gilt_1_price": 100.0,
        "gilt_1_p_date": get_next_tax_year_start(),
        "gilt_1_m_date": get_next_tax_year_start(),
        "gilt_1_pot": "S&S ISA",
        "gilt_1_coupon_pct": 0.0,
        "gilt_2_amt": 0.0,
        "gilt_2_price": 100.0,
        "gilt_2_p_date": get_next_tax_year_start(),
        "gilt_2_m_date": get_next_tax_year_start(),
        "gilt_2_pot": "S&S ISA",
        "gilt_2_coupon_pct": 0.0,
        "gilt_3_amt": 0.0,
        "gilt_3_price": 100.0,
        "gilt_3_p_date": get_next_tax_year_start(),
        "gilt_3_m_date": get_next_tax_year_start(),
        "gilt_3_pot": "S&S ISA",
        "gilt_3_coupon_pct": 0.0,
        "gilt_4_amt": 0.0,
        "gilt_4_price": 100.0,
        "gilt_4_p_date": get_next_tax_year_start(),
        "gilt_4_m_date": get_next_tax_year_start(),
        "gilt_4_pot": "S&S ISA",
        "gilt_4_coupon_pct": 0.0,
        "gilt_5_amt": 0.0,
        "gilt_5_price": 100.0,
        "gilt_5_p_date": get_next_tax_year_start(),
        "gilt_5_m_date": get_next_tax_year_start(),
        "gilt_5_pot": "S&S ISA",
        "gilt_5_coupon_pct": 0.0,
        "crash_pct": 0.0,
        "crash_date": get_next_tax_year_start(),
        "view_mode": "Age Year (Annual)",
        "notes": "",
        "budget_items": [
            {"id": str(uuid.uuid4()), "item": "Housing / Council Tax", "amount": 700.0, "month_paid": "Monthly", "annual_amount": 8400.0},
            {"id": str(uuid.uuid4()), "item": "Utilities & Broadband", "amount": 200.0, "month_paid": "Monthly", "annual_amount": 2400.0},
            {"id": str(uuid.uuid4()), "item": "Groceries", "amount": 350.0, "month_paid": "Monthly", "annual_amount": 4200.0},
            {"id": str(uuid.uuid4()), "item": "Transport & Fuel", "amount": 150.0, "month_paid": "Monthly", "annual_amount": 1800.0},
        ],
    },
}

MONTH_OPTIONS = [
    "Monthly",
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


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

    if "budget_items" not in deserialized:
        deserialized["budget_items"] = []
    else:
        for item in deserialized["budget_items"]:
            if "id" not in item:
                item["id"] = str(uuid.uuid4())
            if "category" in item and "item" not in item:
                item["item"] = item.pop("category")
            if "month_paid" not in item:
                item["month_paid"] = "Monthly"
            if "annual_amount" not in item:
                item["annual_amount"] = item.get("amount", 0.0) * 12.0
    return deserialized


def load_scenarios() -> dict:
    scenarios = {k: v.copy() for k, v in DEFAULT_PROFILES.items()}
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", usecols=[0, 1], ttl=0)
        if not df.empty:
            loaded = {}
            for index, row in df.iterrows():
                if pd.notna(row.get("Profile")) and pd.notna(row.get("JSON_Data")):
                    profile_name = str(row["Profile"])
                    json_string = str(row["JSON_Data"])
                    scen_dict = json.loads(json_string)
                    loaded[profile_name] = deserialize_scenario(scen_dict)
            scenarios.update(loaded)
    except Exception as e:
        pass
    return scenarios


def save_scenarios():
    rows = []
    for name, scen in st.session_state.scenarios.items():
        serialized_scen = serialize_scenario(scen)
        json_string = json.dumps(serialized_scen)
        rows.append({"Profile": name, "JSON_Data": json_string})
    df = pd.DataFrame(rows)
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        conn.update(worksheet="Sheet1", data=df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Failed to save to Google Sheets: {e}")
        st.stop()


# Initialize Session State
if "scenarios" not in st.session_state:
    st.session_state.scenarios = load_scenarios()

if "active_scenario_name" not in st.session_state or st.session_state.active_scenario_name not in st.session_state.scenarios:
    st.session_state.active_scenario_name = list(st.session_state.scenarios.keys())[0]


# ----------------------------------------------------------------------
# 2. Data Models & Reduction Calculation Helper
# ----------------------------------------------------------------------

def calculate_early_retirement_reduction_factor(start_age: float, npa: float = 65.0) -> float:
    """
    Calculates standard UK Public Sector / DB Actuarial Early Retirement Reduction Factor.
    Standard GAD reduction table mapping years early (NPA - start_age) to pension payout factor.
    """
    years_early = max(0.0, npa - start_age)
    if years_early == 0:
        return 1.0
    
    # Standard GAD DB Early Retirement Pension Reduction Factors
    gad_reductions = {
        0: 0.00,
        1: 0.050,
        2: 0.096,
        3: 0.139,
        4: 0.179,
        5: 0.215,
        6: 0.249,
        7: 0.281,
        8: 0.311,
        9: 0.339,
        10: 0.366,
    }
    
    int_years = int(years_early)
    frac = years_early - int_years
    
    base_red = gad_reductions.get(min(int_years, 10), 0.366 + (min(int_years, 10) - 10) * 0.025)
    next_red = gad_reductions.get(min(int_years + 1, 10), base_red + 0.025)
    
    actual_reduction_pct = base_red + (next_red - base_red) * frac
    return max(0.0, 1.0 - actual_reduction_pct)


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
class GiltBond:
    amount: float = 0.0
    purchase_price_pct: float = 100.0
    purchase_date: date = field(default_factory=get_next_tax_year_start)
    maturity_date: date = field(default_factory=get_next_tax_year_start)
    target_pot: str = "S&S ISA"
    coupon_pct: float = 0.0


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
    gilts_bonds: List[GiltBond] = field(default_factory=list)
    state_pension_growth: float = 0.025
    inflation_rate: float = 0.03
    annuity_annual: float = 0.0
    annuity_cost: float = 0.0
    annuity_start_age: int = 65
    annuity_npa: int = 65
    annuity_type: str = "Inflation-Linked (RPI/CPI)"
    inflate_annuity_to_start: bool = False
    apply_db_early_reduction: bool = True
    has_nuvos_pension: bool = False
    nuvos_annual: float = 15929.31
    nuvos_baseline_date: date = field(default_factory=lambda: date(2025, 3, 31))
    nuvos_npa: int = 65
    nuvos_pause_enabled: bool = True
    nuvos_pause_date: date = field(default_factory=get_next_tax_year_start)
    nuvos_salary: float = 57015.0
    nuvos_accrual_rate: float = 2.3
    apply_nuvos_early_reduction: bool = True
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

    @staticmethod
    def _subtract_6_months(d: date) -> date:
        month = d.month - 6
        year = d.year
        if month <= 0:
            month += 12
            year -= 1
        last_day = calendar.monthrange(year, month)[1]
        day = min(d.day, last_day)
        return date(year, month, day)

    def _build_gilt_events(self) -> dict:
        events_map = {}
        for gilt in self.scenario.gilts_bonds:
            if gilt.amount <= 0 or gilt.purchase_date >= gilt.maturity_date:
                continue
            cost = gilt.amount * (gilt.purchase_price_pct / 100.0)
            events_map.setdefault(gilt.purchase_date, []).append(("purchase", cost, gilt.target_pot))
            events_map.setdefault(gilt.maturity_date, []).append(("maturity", gilt.amount, gilt.target_pot))
            annual_coupon_cash = gilt.amount * (gilt.coupon_pct / 100.0)
            if annual_coupon_cash > 0:
                curr = gilt.maturity_date
                coupon_dates = []
                while curr > gilt.purchase_date:
                    coupon_dates.append(curr)
                    curr = self._subtract_6_months(curr)
                coupon_dates.append(curr)
                coupon_dates.sort()
                for i in range(1, len(coupon_dates)):
                    p_start = coupon_dates[i-1]
                    p_end = coupon_dates[i]
                    pay_date = p_end
                    if pay_date > gilt.maturity_date:
                        pay_date = gilt.maturity_date
                    period_total_days = (p_end - p_start).days
                    held_start = max(p_start, gilt.purchase_date)
                    held_end = min(p_end, gilt.maturity_date)
                    held_days = (held_end - held_start).days
                    if period_total_days > 0 and held_days > 0:
                        fraction = held_days / period_total_days
                        coupon_payment = (annual_coupon_cash / 2.0) * fraction
                        events_map.setdefault(pay_date, []).append(("coupon", coupon_payment, gilt.target_pot))
        return events_map

    def run_simulation(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        start_date = date.today()
        try:
            target_100_date = date(self.dob.year + 100, self.dob.month, self.dob.day)
        except ValueError:
            target_100_date = date(self.dob.year + 100, 2, 28)

        # Dynamic Annuity/DB pension start date
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
        
        # Crash & Market Index Recovery tracking variables
        crash_applied = False
        in_market_recovery = False
        market_index = 1.0
        pre_crash_index_target = 1.0
        crash_active_until = None
        crash_capped_income = None
        
        lump_sums_applied = [False] * len(self.scenario.lump_sums)

        gilt_events_map = self._build_gilt_events()

        # Calculate standard DB/Annuity Base Payout with optional Actuarial Reduction
        base_annuity = self.scenario.annuity_annual
        if self.scenario.apply_db_early_reduction and self.scenario.annuity_start_age < self.scenario.annuity_npa:
            db_red_factor = calculate_early_retirement_reduction_factor(self.scenario.annuity_start_age, self.scenario.annuity_npa)
            base_annuity *= db_red_factor

        if self.scenario.inflate_annuity_to_start and annuity_start_date > start_date:
            years_to_start = (annuity_start_date - start_date).days / 365.25
            base_annuity *= ((1.0 + self.scenario.inflation_rate) ** max(0.0, years_to_start))

        # Dynamic Nuvos Accrual & Inflation Engine starting strictly from baseline date
        nuvos_baseline = self.scenario.nuvos_annual if self.scenario.has_nuvos_pension else 0.0
        nuvos_accumulated = nuvos_baseline
        current_nuvos_salary = self.scenario.nuvos_salary

        # Track Nuvos growth timeline from statement baseline date up to Target Retirement Age
        nuvos_sim_date = self.scenario.nuvos_baseline_date
        try:
            ret_date_limit = date(self.dob.year + self.retirement_age, self.dob.month, self.dob.day)
        except ValueError:
            ret_date_limit = date(self.dob.year + self.retirement_age, 2, 28)

        # Pre-simulate Nuvos growth from March 2025 baseline to today (start_date)
        if self.scenario.has_nuvos_pension and nuvos_sim_date < start_date:
            curr_sim = nuvos_sim_date + timedelta(days=1)
            while curr_sim <= start_date:
                if curr_sim.day == 1 and curr_sim.month == 4:
                    nuvos_accumulated *= (1.0 + self.scenario.inflation_rate)
                    if not self.scenario.nuvos_pause_enabled or curr_sim <= self.scenario.nuvos_pause_date:
                        current_nuvos_salary *= (1.0 + self.scenario.inflation_rate)
                        new_accrual = current_nuvos_salary * (self.scenario.nuvos_accrual_rate / 100.0)
                        nuvos_accumulated += new_accrual
                curr_sim += timedelta(days=1)

        # Calculate finalized Nuvos payout at Target Retirement Age including Early Reduction Factor
        nuvos_payout_at_retire = 0.0
        nuvos_calculated_at_retire = False

        while current_date <= target_100_date:
            age = self._calculate_age(self.dob, current_date)
            is_retired = age >= self.retirement_age
            current_tax_year = self._get_tax_year(current_date)

            if current_tax_year != last_tax_year:
                taxable_income_this_tax_year = 0.0
                isa_credited_this_tax_year = 0.0
                last_tax_year = current_tax_year

            # Ongoing Nuvos Active Accrual vs Inflation Revaluation Check (from start_date forward)
            if self.scenario.has_nuvos_pension and current_date < ret_date_limit:
                if current_date > start_date and current_date.day == 1 and current_date.month == 4:
                    nuvos_accumulated *= (1.0 + self.scenario.inflation_rate)
                    active_accrual_active = not self.scenario.nuvos_pause_enabled or (current_date <= self.scenario.nuvos_pause_date)
                    if active_accrual_active:
                        current_nuvos_salary *= (1.0 + self.scenario.inflation_rate)
                        new_accrual = current_nuvos_salary * (self.scenario.nuvos_accrual_rate / 100.0)
                        nuvos_accumulated += new_accrual

            # Apply early retirement actuarial reduction factor to Nuvos pension at retirement age
            if self.scenario.has_nuvos_pension and current_date >= ret_date_limit and not nuvos_calculated_at_retire:
                unreduced_nuvos = nuvos_accumulated
                if self.scenario.apply_nuvos_early_reduction and self.retirement_age < self.scenario.nuvos_npa:
                    reduction_factor = calculate_early_retirement_reduction_factor(self.retirement_age, self.scenario.nuvos_npa)
                    nuvos_payout_at_retire = unreduced_nuvos * reduction_factor
                else:
                    nuvos_payout_at_retire = unreduced_nuvos
                nuvos_calculated_at_retire = True

            # Standard Annuity Calculation
            current_annual_annuity = 0.0
            if current_date >= annuity_start_date and base_annuity > 0:
                if self.scenario.annuity_type == "Flat Rate (Level)":
                    current_annual_annuity = base_annuity
                else:
                    years_since_annuity = current_date.year - annuity_start_date.year - (
                        (current_date.month, current_date.day) < (annuity_start_date.month, annuity_start_date.day)
                    )
                    current_annual_annuity = base_annuity * (
                        (1.0 + self.scenario.inflation_rate) ** max(0, years_since_annuity)
                    )

            # Nuvos Annual Payout escalating post-retirement with CPI
            current_annual_nuvos = 0.0
            if self.scenario.has_nuvos_pension and current_date >= ret_date_limit:
                years_since_nuvos_start = current_date.year - ret_date_limit.year - (
                    (current_date.month, current_date.day) < (ret_date_limit.month, ret_date_limit.day)
                )
                current_annual_nuvos = nuvos_payout_at_retire * ((1.0 + self.scenario.inflation_rate) ** max(0, years_since_nuvos_start))

            total_combined_annual_pension = current_annual_annuity + current_annual_nuvos

            # Lump sum injections processing
            for idx, ls in enumerate(self.scenario.lump_sums):
                if not lump_sums_applied[idx] and ls.amount != 0 and current_date >= ls.injection_date:
                    if ls.amount > 0:
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

            daily_gilt_income = 0.0
            if current_date in gilt_events_map:
                for ev_type, amt, target_pot in gilt_events_map[current_date]:
                    if ev_type == "purchase":
                        rem_cost = amt
                        if target_pot == "SIPP":
                            sipp = max(0.0, sipp - rem_cost)
                        elif target_pot == "Private Pension":
                            total_wp = wp_taxable + wp_tax_free
                            total_wp = max(0.0, total_wp - rem_cost)
                            wp_taxable = total_wp * 0.75
                            wp_tax_free = total_wp * 0.25
                        elif target_pot == "S&S ISA":
                            isa = max(0.0, isa - rem_cost)
                        elif target_pot == "Other Investment":
                            other = max(0.0, other - rem_cost)
                    elif ev_type in ("coupon", "maturity"):
                        daily_gilt_income += amt
                        if target_pot == "SIPP":
                            sipp += amt
                        elif target_pot == "Private Pension":
                            wp_taxable += amt * 0.75
                            wp_tax_free += amt * 0.25
                        elif target_pot == "S&S ISA":
                            isa += amt
                        elif target_pot == "Other Investment":
                            other += amt

            # ------------------------------------------------------------------
            # Market Crash Trigger & Market Recovery Tracking
            # ------------------------------------------------------------------
            if (
                not crash_applied
                and self.scenario.crash_pct > 0
                and current_date >= self.scenario.crash_date
            ):
                pre_crash_index_target = market_index
                drop_factor = 1.0 - (self.scenario.crash_pct / 100.0)
                
                sipp *= drop_factor
                wp_taxable *= drop_factor
                wp_tax_free *= drop_factor
                isa *= drop_factor
                market_index *= drop_factor
                
                crash_applied = True
                in_market_recovery = True
                
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

            if not is_retired and current_date.day == 1:
                sipp += self.scenario.sipp.monthly_contrib
                wp_taxable += self.scenario.workplace_taxable.monthly_contrib
                wp_tax_free += self.scenario.workplace_tax_free.monthly_contrib
                isa += self.scenario.isa.monthly_contrib
                other += self.scenario.other_investment.monthly_contrib

            # ------------------------------------------------------------------
            # Dynamic Pot Growth & Accelerated Rebound Return Multiplier
            # ------------------------------------------------------------------
            if in_market_recovery and market_index >= pre_crash_index_target:
                in_market_recovery = False

            return_mult = 2.0 if in_market_recovery else 1.0

            effective_sipp_ret = self.scenario.sipp.annual_return * return_mult
            effective_wp_ret = self.scenario.workplace_pension_return * return_mult
            effective_isa_ret = self.scenario.isa.annual_return * return_mult

            sipp *= 1.0 + self._get_daily_rate(effective_sipp_ret)
            wp_taxable *= 1.0 + self._get_daily_rate(effective_wp_ret)
            wp_tax_free *= 1.0 + self._get_daily_rate(effective_wp_ret)
            isa *= 1.0 + self._get_daily_rate(effective_isa_ret)
            
            market_index *= 1.0 + self._get_daily_rate(effective_isa_ret)

            other_growth = other * self._get_daily_rate(self.scenario.other_investment.annual_return)
            other_tax_on_growth = other_growth * 0.18
            other += (other_growth - other_tax_on_growth)

            monthly_drawn_from_pots = 0.0
            draw_sipp_amt = 0.0
            draw_wp_taxable_amt = 0.0
            draw_wp_taxfree_amt = 0.0
            draw_isa_amt = 0.0
            draw_other_amt = 0.0

            state_pension_monthly = 0.0
            combined_pension_monthly = 0.0
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

            if is_retired and current_date.day == 1:
                if total_combined_annual_pension > 0:
                    combined_pension_monthly = total_combined_annual_pension / 12.0
                    taxable_income_this_tax_year += combined_pension_monthly

                if (
                    self.scenario.has_state_pension
                    and age >= self.scenario.state_pension_age
                ):
                    inflated_state_pension_annual = self.scenario.state_pension_amount * (
                        (1.0 + self.scenario.state_pension_growth) ** years_since_start
                    )
                    state_pension_monthly = inflated_state_pension_annual / 12.0
                    taxable_income_this_tax_year += state_pension_monthly

                guaranteed_monthly_income = combined_pension_monthly + state_pension_monthly

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
                        draw_other_amt += draw
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
                            s_share = (sipp / tot_taxable) if tot_taxable > 0 else 0.0
                            wp_share = (wp_taxable / tot_taxable) if tot_taxable > 0 else 0.0
                            s_draw = draw * s_share
                            wp_draw = draw * wp_share
                            sipp -= s_draw
                            wp_taxable -= wp_draw
                            draw_sipp_amt += s_draw
                            draw_wp_taxable_amt += wp_draw
                            taxable_income_this_tax_year += draw
                            needed_net -= draw
                            monthly_drawn_from_pots += draw

                    if needed_net > 0 and isa > 0:
                        draw = min(isa, needed_net)
                        isa -= draw
                        needed_net -= draw
                        draw_isa_amt += draw
                        monthly_drawn_from_pots += draw

                    if needed_net > 0 and wp_tax_free > 0:
                        draw = min(wp_tax_free, needed_net)
                        wp_tax_free -= draw
                        needed_net -= draw
                        draw_wp_taxfree_amt += draw
                        monthly_drawn_from_pots += draw

                    tot_taxable = sipp + wp_taxable
                    if needed_net > 0 and tot_taxable > 0:
                        gross_needed = needed_net / (1.0 - self.BASIC_TAX_RATE)
                        gross_draw = min(tot_taxable, gross_needed)
                        if gross_draw > 0:
                            s_share = (sipp / tot_taxable) if tot_taxable > 0 else 0.0
                            wp_share = (wp_taxable / tot_taxable) if tot_taxable > 0 else 0.0
                            s_draw = gross_draw * s_share
                            wp_draw = gross_draw * wp_share
                            sipp -= s_draw
                            wp_taxable -= wp_draw
                            draw_sipp_amt += s_draw
                            draw_wp_taxable_amt += wp_draw
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
                        draw_other_amt += draw
                        monthly_drawn_from_pots += draw

                if needed_net > 0:
                    cumulative_deficit += needed_net

            private_pension_val = wp_taxable + wp_tax_free
            total_portfolio = (sipp + wp_taxable + wp_tax_free + isa + other) - cumulative_deficit
            total_monthly_income = monthly_drawn_from_pots + state_pension_monthly + combined_pension_monthly
            
            total_daily_investment_income = daily_gilt_income

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
                "investment_income": int(round(total_daily_investment_income)),
                "total_portfolio": int(round(total_portfolio)),
                "annuity_income": int(round(total_combined_annual_pension if is_retired else 0.0)),
                "state_pension_income": int(round(state_pension_monthly)),
                "pot_income_drawn": int(round(monthly_drawn_from_pots)),
                "draw_sipp": draw_sipp_amt,
                "draw_wp_taxable": draw_wp_taxable_amt,
                "draw_wp_taxfree": draw_wp_taxfree_amt,
                "draw_isa": draw_isa_amt,
                "draw_other": draw_other_amt,
                "monthly_net_income": int(round(total_monthly_income)),
                "tax_paid": int(round(tax_paid)),
            })
            current_date += timedelta(days=1)

        df = pd.DataFrame(daily_records)
        monthly_df = (
            df.groupby("raw_month")
            .agg({
                "date": "last", "age": "last", "is_retired": "last",
                "desired_monthly_income": "last", "desired_annual_income": "last",
                "sipp": "last", "private_pension": "last", "isa": "last",
                "other_investment": "last", "investment_income": "sum",
                "total_portfolio": "last", "annuity_income": "last",
                "state_pension_income": "sum", "pot_income_drawn": "sum",
                "draw_sipp": "sum", "draw_wp_taxable": "sum", "draw_wp_taxfree": "sum",
