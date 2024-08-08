import timeit

total = 0


def time(package: str) -> None:
    global total
    t = timeit.timeit(f"import {package}", number=1)
    total += t
    print(f"{package:<20} {t:.3f} s")


print("Ready")
print("-" * 28)

time("args")
time("autochecklist")
time("captions")
time("config")
time("external_services")
time("lib")

print("-" * 28)
print(f"{'Total':<20} {total:.3f} s")
