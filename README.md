# .dotfiles

Tracking .dotfiles

0. Get the `install` the script onto the machine using:
```bash
$ curl https://raw.githubusercontent.com/bdatko/.dotfiles/refs/heads/main/install > install
```
1. Then make the script executable:
```bash
$ chmod u+x install
```
3. Run the install script
```bash
$ ./install
```
The `install` script will install `homebrew` and `stow`. Once you have both you can clone this directory.

Below is an example on how this repo integrates with GNU `stow`

```bash
$ stow -R --dotfiles zsh scripts install-scripts git alacritty
```
