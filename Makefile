.DEFAULT_GOAL := help

.PHONY: design
design: ## Open Qt Designer, usage : make design file=forms/MyForm.ui
	@echo "Running Qt Designer on ciclone/$(file)"
	@mkdir -p ciclone/$(dir $(file))
	@open -a "/Applications/Qt Creator.app" ciclone/$(file)

.PHONY: help
help: ## Display this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'