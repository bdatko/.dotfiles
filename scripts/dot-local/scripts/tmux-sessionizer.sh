#!/usr/bin/env bash

selected=$( (echo "Home"; echo "Downloads"; find ~/work ~/personal -maxdepth 1 -mindepth 1 -type d) | fzf)
if [[ -z "$selected" ]]; then
    exit 0
fi

selected_name=$(basename $selected | tr ".,: " "____")

if [[ "$selected" == "Home" ]]; then
    selected=$HOME
    selected_name="HOME"
elif [[ "$selected" == "Downloads" ]]; then
    selected="$HOME/Downloads"
    selected_name="Downloads"
fi


switch_to() {
    if [[ -z "$TMUX" ]]; then 
        tmux attach-session -t $selected_name
    else
        tmux switch-client -t $selected_name
    fi
}

if tmux has-session -t="$selected_name" 2> /dev/null; then
    switch_to
else
    tmux new-session -ds $selected_name -c $selected
    switch_to
fi

