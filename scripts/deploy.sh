session=app
tmux select-pane -t $session:0
tmux kill-session -t $session
tmux new-session -d -s $session -c aichatsback
tmux select-pane -t $session:0
command="git pull && python3 -m uvicorn app:app --port 1605 "
tmux send-keys "$command" Enter
