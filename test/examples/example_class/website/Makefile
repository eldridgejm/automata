.PHONY: website
website: clean
	mkdir _build
	publish .. _build/published --skip-directories template
	abstract _build --published _build/published --context ../course.yaml

.PHONY: clean
clean:
	rm -rf _build
