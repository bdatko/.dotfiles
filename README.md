# .dotfiles

macOS dotfiles managed with [GNU Stow](https://www.gnu.org/software/stow/).
Everything here is plain text; secrets and machine identity live in untracked
`*.local` files.

## Layout

A Stow **package** is a top-level directory. Dot-prefixed names are written
`dot-…` and `--dotfiles` turns them back into `.…` at the target.

| Package | Stows into | Contents |
| --- | --- | --- |
| `alacritty` | `~/.config/alacritty` | terminal config |
| `git` | `~/.config/git` | global gitignore |
| `gitconfig` | `~/.gitconfig` | shared git config (identity comes from `~/.gitconfig.local`) |
| `install-scripts` | `~/.local/share/install-scripts` | one script per package, run by [babo](https://github.com/bdatko/babo) |
| `scripts` | `~/.local/scripts` | small shell utilities |
| `tmux` | `~/.config/tmux` | tmux config |
| `zsh` | `~/.zshrc`, `~/.zprofile` | zsh config |

Intentionally **not** stowed by default:

- `nvim` — it conflicts with a real `~/.config/nvim` clone (see below).
- `jupyter` — valid package, not currently used.
- `tests` — harness, not a package.

`stow-packages` is the source of truth for what gets stowed. GNU Stow does not
discover packages on its own, so every package must be listed there. (GNU Stow
has called them "packages" since 2.0; "modules" is the old term.)

## New machine

### 1. Clone the repo

```bash
git clone --recurse-submodules https://github.com/bdatko/.dotfiles.git ~/.dotfiles
cd ~/.dotfiles

# Read the bootstrap before running it.
less install
```

HTTPS works without SSH keys on a fresh machine. Switch the remote to SSH later
if you want to push:

```bash
git remote set-url origin git@github.com:bdatko/.dotfiles.git
```

### 2. Homebrew and Stow

```bash
cd ~/.dotfiles
./install
```

`install` downloads Homebrew's upstream installer to a temporary file and runs
it from disk, appends `brew shellenv` to `~/.zprofile.local` (idempotently),
and installs `stow`.

### 3. uv

`uv` is a bootstrap prerequisite: both `./stow-all.py` and `babo` run on it.

First put Homebrew on `PATH` in this shell — open a new terminal, or:

```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
```

Then install uv from Homebrew rather than piping a remote script into a shell:

```bash
brew install uv
```

### 4. babo

```bash
uv tool install git+https://github.com/bdatko/babo.git
uv tool update-shell
```

Run `uv tool update-shell` **before** stowing `zsh`. It edits shell rc files,
and `~/.zshrc` is a Stow symlink, so running it later dirties this repo.

### 5. Stow

```bash
# Stow refuses to overwrite a real ~/.zprofile.
[ -e ~/.zprofile ] && [ ! -L ~/.zprofile ] && mv ~/.zprofile ~/.zprofile.bak

cd ~/.dotfiles
./stow-all.py -n -v   # simulate
./stow-all.py         # apply
```

`./stow-all.py` runs `stow -R --dotfiles` for every package in
`stow-packages`; extra flags are forwarded to Stow (`--dry-run` is sugar for
`-n`).

### 6. Packages

Install scripts are executed with babo:

```bash
babo install --dry-run --target-dir ~/.local/share/install-scripts/
babo install --target-dir ~/.local/share/install-scripts/

# One package at a time (PICK is a regex on the script name stem):
babo install --target-dir ~/.local/share/install-scripts/ gopls
```

Babo runs every executable file in the target directory and skips the rest, so
adding a script is all that is needed. It also honours
`BABO_TARGET_DIR`.

### 7. Verify

```bash
cd ~/.dotfiles
./check-brew.py
uv run tests/tmux.py
```

## Download trust model

Nothing is executed from a pipe. The dotfiles arrive via `git clone`, `uv`
comes from Homebrew, and `install` downloads Homebrew's upstream installer to a
temporary file before running it. The only other download is the Alacritty
fallback, which pins a version and verifies the release's SHA256 before
mounting it.

Residual assumptions:

- The Homebrew installer is fetched from upstream `HEAD` and is not checksummed
  here. Pinning it would be misleading, because the installer clones
  `Homebrew/brew` at `HEAD` anyway.
- Commits in this repo are not signed, so a clone can be inspected but not
  cryptographically attributed.
- The Alacritty fallback intentionally bypasses Gatekeeper: the cask is
  disabled for `fails_gatekeeper_check`, and `curl` downloads are not
  quarantined. The digest proves it is the exact GitHub artifact, not that
  Apple trusts it.

## Machine-local files

These are untracked (`.gitignore` contains `*.local`) and must be created by
hand on each machine. The README deliberately does not include their contents.

| File | Purpose |
| --- | --- |
| `~/.gitconfig.local` | default `user.name` / `user.email`, included by the tracked git config |
| `~/.gitconfig-personal` | identity and overrides for `~/personal/` and `~/.dotfiles/` |
| `~/.gitconfig-work` | identity and overrides for `~/work/` |
| `~/.zprofile.local` | machine-only login-shell setup (secret env, brew shellenv) |

`~/.gitconfig.local` is not just a backup. The tracked config sets
`user.useConfigOnly = true`, so git refuses to guess an identity. Repos outside
the three `includeIf` paths — `~/.config/nvim` is one — get their identity from
`~/.gitconfig.local`.

Precedence:

1. `~/.gitconfig.local` supplies the fallback identity.
2. `[includeIf]` blocks in `~/.gitconfig` override it inside `~/personal/`,
   `~/work/`, and `~/.dotfiles/`.
3. Everything else keeps the fallback.

## Git credentials (OAuth)

The tracked `~/.gitconfig` enables the OAuth helper globally, last in the chain:

```ini
[credential]
    helper = oauth
```

macOS already contributes `osxkeychain` from the system git config, so the
effective chain is `osxkeychain` (storage) then `oauth` (generator). The OAuth
helper must come last; see the **OAuth** section of
[`gitcredentials(7)`](https://git-scm.com/docs/gitcredentials#_oauth).

[`git-credential-oauth`](https://github.com/hickford/git-credential-oauth) is
recommended by git's own documentation. It requires git ≥ 2.45 for refresh
token storage and is installed by `install-scripts/…/git-credential-oauth.sh`.

Caveats:

- **Do not run `git credential-oauth configure`.** It writes to `~/.gitconfig`,
  which is a symlink into this repo, and would dirty the working tree. Edit the
  tracked file instead.
- **Do not use `git config --global` for machine-specific values**, for the same
  reason. Put them in `~/.gitconfig.local` or another untracked file.
- To clear a stale credential:
  `printf "protocol=https\nhost=gitlab.com\n" | git credential reject`.
- Check where helpers come from:
  `git config --show-origin --get-all credential.helper`.

## Neovim

There are two mutually exclusive shapes; pick one per machine.

**Shape A — stow it.** Remove `nvim` from the "not listed" section of
`stow-packages` and run `./stow-all.py`. `~/.config/nvim` becomes a symlink
into `nvim/dot-config/nvim`, which is a git submodule pinned by this repo.

**Shape B — keep a real clone.** This machine uses Shape B:
`~/.config/nvim` is its own clone, and `nvim/dot-config/nvim` merely records
the commit. Updating the submodule does not change the live config; push from
`~/.config/nvim` directly.

Update the pinned submodule:

```bash
git -C ~/.dotfiles submodule update --remote nvim/dot-config/nvim
```

## Alacritty

The `alacritty` homebrew-cask is disabled because it does not pass the macOS
Gatekeeper check, and Homebrew 7 removed `--no-quarantine`. `alacritty.sh`
prefers the cask when Homebrew can provision it; otherwise it downloads a
pinned upstream release, verifies the SHA256 published for that asset, checks
that the bundle identifier is `org.alacritty`, and copies `Alacritty.app` into
`/Applications` (no elevation needed). Because the download uses `curl`, the
app is not quarantined — this intentionally bypasses Gatekeeper, the same net
effect as the old `--no-quarantine` flag. The script carries
`# check-brew: allow-unavailable` so `check-brew.py` does not flag the
intentionally disabled cask.

To bump the fallback, update `ALACRITTY_VERSION` and `ALACRITTY_SHA256` in
`alacritty.sh`. The digest is the asset's `sha256` from GitHub's release API.

## tmux

Config lives in `tmux/dot-config/tmux/tmux.conf` and is stowed as
`~/.config/tmux/tmux.conf`. `terminal-features` is set with a complete list in
a single idempotent `set -s`, so reloading never duplicates entries.

Tests run against a throwaway socket, never the default server:

```bash
uv run tests/tmux.py           # all checks
uv run tests/tmux.py --live    # also compare the running server version
uv run tests/tmux.py -o features -o idempotence
```

Output is one `== <check> == PASS|FAIL` line per check; the exit status is
nonzero on failure.

## Checks

```bash
./stow-all.py -n -v   # no stow conflicts
./check-brew.py       # declared packages are installed
./check-brew.py -v    # also list what each file declares
./check-brew.py --strict  # also fail on undeclared or unprovisionable packages
uv run tests/tmux.py  # tmux config
```

`check-brew.py` compares `brew install` lines in `install-scripts/` and
`install` against `brew list --formula` and `brew list --cask`. Personal
packages that should not be provisioned are listed in `brew-ignore` (fnmatch
globs work). It also warns when a declared package cannot be installed on a
fresh machine — disabled or deprecated, or removed from every tap and left as
a keg-local formula. `--strict` turns that warning into a failure. A script
that intentionally installs such a package out-of-band can opt out with
`# check-brew: allow-unavailable`.

## Adding a package

1. Create a top-level directory and name files `dot-…` for dotfiles, e.g.
   `mytool/dot-config/mytool/config.toml`.
2. Add `mytool` to `stow-packages`.
3. `./stow-all.py -n -v`, then `./stow-all.py`.
4. For system packages, add `install-scripts/dot-local/share/install-scripts/mytool.sh`
   (`brew install …`, executable) and run `./check-brew.py`.

## Updating

```bash
cd ~/.dotfiles
git pull
git submodule update --init --recursive
./stow-all.py
./check-brew.py
uv run tests/tmux.py
```

If a new install script appeared, run `babo install --target-dir
~/.local/share/install-scripts/` (or pass its name to install just that one).
