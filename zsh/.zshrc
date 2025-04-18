eval "$(starship init zsh)"

source $(brew --prefix)/Cellar/fzf/$(fzf --version | cut -d ' ' -f 1)/shell/key-bindings.zsh
