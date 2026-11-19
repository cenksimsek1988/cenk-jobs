"""A pay figure in another currency, at the European Central Bank's reference rate of the day, rounded up.

    fx.py <amount> <from> <to> [--rates <file>]

Prints one line, which the answer record keeps as the answer's note. Example:
    fx.py 60000 EUR USD  ->  60000 EUR = 64872 USD (ECB 1.0812, 2026-11-19)
The rates are the ECB's daily reference rates against the euro (eurofxref-daily.xml); a pair without the euro goes
through it. --rates <file>: that XML saved before (tests, or no network). A currency the ECB does not list exits 1.
"""
import math
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

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


def main():
    args = sys.argv[1:]
    path = None
    if "--rates" in args:
        i = args.index("--rates")
        if i + 1 >= len(args):
            sys.exit("--rates takes a saved eurofxref-daily.xml")
        path = args[i + 1]
        del args[i:i + 2]
    if len(args) != 3 or not re.fullmatch(r"\d+(\.\d+)?", args[0].replace(",", "")):
        sys.exit(__doc__)
    amount, src, dst = float(args[0].replace(",", "")), args[1].upper(), args[2].upper()
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
    print(f"{args[0]} {src} = {math.ceil(round(amount * rate, 4))} {dst} (ECB {rate:.4f}, {day})")


if __name__ == "__main__":
    main()
