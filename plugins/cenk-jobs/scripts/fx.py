"""A pay figure as it is typed into a form: in another currency at the European Central Bank's reference rate of the
day, rounded up, and in every case rounded up until its significant part ends in 0 or 5 (paylib.py).

    fx.py <amount> <from> <to> --per year|month|day|hour [--rates <file>]

Prints one line, which the answer record keeps as the answer's note; the figure after "typed:" is the one the form
gets. Examples:
    fx.py 60000 EUR USD --per year  ->  60000 EUR a year = 64872 USD; typed: 65000 USD (ECB 1.0812, 2026-11-19)
    fx.py 87920 USD USD --per year  ->  87920 USD a year; typed: 90000 USD
The same currency twice needs no rate and no network. The rates are the ECB's daily reference rates against the euro
(eurofxref-daily.xml); a pair without the euro goes through it. --rates <file>: that XML saved before (tests, or no
network). A currency the ECB does not list exits 1.
"""
import math
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paylib  # noqa: E402

ECB = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"


def rates_from(xml_text):
    """({currency: units per euro}, date) from the ECB's daily XML; EUR is 1."""
    root = ET.fromstring(xml_text)
    rates, day = {"EUR": 1.0}, ""
    for el in root.iter():
        if el.tag.endswith("Cube") and el.get("time"):
            day = el.get("time")
        if el.tag.endswith("Cube") and el.get("currency") and el.get("rate"):
            rates[el.get("currency").upper()] = float(el.get("rate"))
    return rates, day


def option(args, name):
    """The value after name, removed from args; "" when name is not there."""
    if name not in args:
        return ""
    i = args.index(name)
    if i + 1 >= len(args):
        sys.exit(__doc__)
    value = args[i + 1]
    del args[i:i + 2]
    return value


def main():
    args = sys.argv[1:]
    path, per = option(args, "--rates"), option(args, "--per").lower()
    if len(args) != 3 or not re.fullmatch(r"\d+(\.\d+)?", args[0].replace(",", "")):
        sys.exit(__doc__)
    if per not in paylib.PERIODS:
        sys.exit(f"--per {'|'.join(paylib.PERIODS)}: the typed figure's rounding depends on it (0.46.5)\n" + __doc__)
    amount, src, dst = float(args[0].replace(",", "")), args[1].upper(), args[2].upper()
    if src == dst:
        print(f"{args[0]} {src} a {per}; typed: {paylib.typed(amount, dst, per)} {dst}")
        return
    if path:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    else:
        req = urllib.request.Request(ECB, headers={"User-Agent": "cenk-jobs fx"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                text = resp.read().decode("utf-8")
        except OSError as e:  # URLError and TLS failures are OSErrors
            print(f"fx: ECB rates not fetched from {ECB}: {e} -> save it with curl, then pass --rates <file>",
                  file=sys.stderr)
            sys.exit(2)
    rates, day = rates_from(text)
    missing = [c for c in (src, dst) if c not in rates]
    if missing:
        print(f"no ECB rate for {', '.join(missing)} on {day or 'that day'}", file=sys.stderr)
        sys.exit(1)
    rate = rates[dst] / rates[src]
    # Rounded to 4 places before rounding up: 64872 / 1.0812 is 60000.000000001 in floating point, not 60001.
    converted = math.ceil(round(amount * rate, 4))
    print(f"{args[0]} {src} a {per} = {converted} {dst}; typed: {paylib.typed(converted, dst, per)} {dst} "
          f"(ECB {rate:.4f}, {day})")


if __name__ == "__main__":
    main()
