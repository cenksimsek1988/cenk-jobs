"""The pay figure typed into a form: rounded up until its significant part ends in 0 or 5.

The significant part is the figure counted in the unit that currency's salaries are usually counted in, rounded up to
a whole number: thousands a year, hundreds a month, tens a day, ones an hour, unless COUNTED_IN names another unit for
the currency (TRY: thousands a month too; JPY: ten thousands). It then goes up to the next whole number ending in 0 or 5, and the typed
figure is that number of units. A figure already there stays as it is.
Examples: 87,920 USD a year -> 87.92 thousand -> 88 -> 90 -> 90,000; 6,667 EUR a month -> 66.67 hundred -> 67 -> 70 ->
7,000; 14,700 EUR a month -> 147 hundred -> 150 -> 15,000; 220,000 TRY a month -> 220 thousand -> 220,000.
Used by fx.py, which prints the typed figure for the session, the funnel and the brief.
"""
import math

PERIODS = ("year", "month", "day", "hour")
UNIT = {"year": 1000, "month": 100, "day": 10, "hour": 1}
# A currency whose salaries are counted in another unit than UNIT gives: {currency: {period: unit}}. Add one where its
# usual way of saying a salary differs. Examples: TRY's "220 bin" a month is counted in thousands, JPY's "500万" a year
# in ten thousands, INR's "15 lakh" a year in hundred thousands.
COUNTED_IN = {"TRY": {"year": 1000, "month": 1000}, "JPY": {"year": 10000, "month": 10000},
              "KRW": {"year": 1000000, "month": 10000}, "INR": {"year": 100000, "month": 1000},
              "HUF": {"month": 1000}, "CZK": {"month": 1000}, "SEK": {"month": 1000}, "NOK": {"month": 1000},
              "DKK": {"month": 1000}, "RUB": {"month": 1000}}


def unit(currency, per):
    """The unit a salary in this currency and period is counted in. Example: ("EUR", "month") -> 100."""
    if per not in UNIT:
        raise ValueError(f"the period is one of {', '.join(PERIODS)}: got {per!r}")
    return COUNTED_IN.get(str(currency).upper(), {}).get(per, UNIT[per])


def typed(amount, currency, per):
    """The figure to type for this amount: rounded up so its significant part ends in 0 or 5. Example: (87920, "USD",
    "year") -> 90000."""
    u = unit(currency, per)
    part = math.ceil(round(float(amount) / u, 6))  # 6 places first: 6700 / 100 is 67.00000000000001 in floating point
    return math.ceil(part / 5) * 5 * u
