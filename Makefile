.PHONY: check serve

check:
	python3 scripts/check_site.py

serve:
	python3 -m http.server 4180 --bind 127.0.0.1
