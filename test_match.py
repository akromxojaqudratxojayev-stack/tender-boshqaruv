import re

html = open('xt_html.txt', encoding='utf-8').read()
matches = re.findall(r'name="totalcost_clone"[^>]+title="([^"]+)"', html)
print("totalcost_clone title matches:", matches)

matches_value = re.findall(r'name="totalcost"[^>]+value="([^"]+)"', html)
print("totalcost value matches:", matches_value)
