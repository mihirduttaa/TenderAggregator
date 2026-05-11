#!/usr/bin/env python3

text = "supply of water supply related motors submersible pumps pipes and other fitting materials miscellaneous goods"

keywords_water = [
    "water supply", "pipeline", "drinking water", "drainage", "sewage",
    "borewell", "submersible", "water tank", "overhead tank", "sewerage",
    "handpump", "tubewell", "water treatment", "nal jal", "jal jeevan",
    "sewer", "naali", "nala", "PAC", "ferric alum", "water chemical",
    "pump house", "submersible pump", "motor set", "water supply maintenance",
    "water maintenance"
]

print("Text:", text)
print("\nMatching keywords:")
for kw in keywords_water:
    if kw.lower() in text:
        print(f"  ✓ '{kw}' found")

print("\nFirst match:", next((kw for kw in keywords_water if kw.lower() in text), None))
