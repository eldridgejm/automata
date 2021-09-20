.PHONY: website
website: clean
	mkdir _build
	automata materials publish --input-directory .. _build/materials --skip-directories template
	automata coursepage build --materials _build/materials _build --vars ../course.yaml

.PHONY: clean
clean:
	rm -rf _build
