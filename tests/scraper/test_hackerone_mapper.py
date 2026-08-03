import json

from db.mapper.hackerone_mapper import HackerOneMapper

with open("test_detail_output.json", "r", encoding="utf-8") as f:
    programs = json.load(f)

# Test the first scraped program
scraped_program = programs[0]

mapped = HackerOneMapper.map_program(scraped_program)

print("=" * 80)
print("MASTER")
print("=" * 80)
print(mapped["master"])

print()

print("=" * 80)
print("FIRST SCOPE")
print("=" * 80)
print(mapped["scopes"][1] if mapped["scopes"] else "No scopes")

print()

print("=" * 80)
print("FIRST WEAKNESS")
print("=" * 80)
print(mapped["weaknesses"][1] if mapped["weaknesses"] else "No weaknesses")

print()

print("=" * 80)
print("FIRST EXCLUSION")
print("=" * 80)
print(mapped["exclusions"][1] if mapped["exclusions"] else "No exclusions")