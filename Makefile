.PHONY: build check render-social-preview serve serve-dist

build: check
	python3 scripts/build_site.py

check:
	python3 scripts/check_site.py

render-social-preview:
	bash scripts/render_social_preview.sh

serve:
	python3 -m http.server 4180 --bind 127.0.0.1

serve-dist: build
	python3 -m http.server 4181 --bind 127.0.0.1 --directory dist
