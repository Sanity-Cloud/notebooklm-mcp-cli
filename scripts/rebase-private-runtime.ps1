param(
    [string] $StackWorktree = 'X:\Code\worktrees\nlm-upstream-stack-20260805',
    [string] $PrivateWorktree = 'X:\Code\worktrees\nlm-private-layered-20260805',
    [string] $UpstreamRemote = 'origin',
    [string] $UpstreamBranch = 'main',
    [switch] $Apply,
    [switch] $SkipTests
)

$ErrorActionPreference = 'Stop'

function Invoke-Git([string] $Worktree, [string[]] $Arguments) {
    & git -C $Worktree @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed in $Worktree with exit code $LASTEXITCODE"
    }
}

function Assert-Clean([string] $Worktree) {
    $status = & git -C $Worktree status --porcelain
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read Git status in $Worktree"
    }
    if ($status) {
        throw "Worktree is not clean: $Worktree"
    }
}

Assert-Clean $StackWorktree
Assert-Clean $PrivateWorktree

Invoke-Git $StackWorktree @('fetch', '--prune', $UpstreamRemote)
$upstreamRef = "$UpstreamRemote/$UpstreamBranch"
$oldStack = (& git -C $StackWorktree rev-parse HEAD).Trim()
$oldPrivate = (& git -C $PrivateWorktree rev-parse HEAD).Trim()
$upstreamHead = (& git -C $StackWorktree rev-parse $upstreamRef).Trim()
$timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')

Write-Output "Upstream: $upstreamRef $upstreamHead"
Write-Output "Stack:    $oldStack"
Write-Output "Private:  $oldPrivate"
Write-Output "Stack divergence (upstream...stack):"
& git -C $StackWorktree rev-list --left-right --count "$upstreamRef...HEAD"

if (-not $Apply) {
    Write-Output 'Dry run complete. Re-run with -Apply to create backups, rebase, and validate.'
    exit 0
}

Invoke-Git $StackWorktree @('branch', "backup/upstream-stack-$timestamp", $oldStack)
Invoke-Git $PrivateWorktree @('branch', "backup/private-layer-$timestamp", $oldPrivate)
Invoke-Git $StackWorktree @('rebase', $upstreamRef)
$newStack = (& git -C $StackWorktree rev-parse HEAD).Trim()
Invoke-Git $PrivateWorktree @('rebase', '--onto', $newStack, $oldStack)

if (-not $SkipTests) {
    & uv --directory $StackWorktree run ruff check .
    if ($LASTEXITCODE -ne 0) { throw 'Upstream stack lint failed.' }
    & uv --directory $StackWorktree run pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Upstream stack tests failed.' }
    & uv --directory $PrivateWorktree run ruff check .
    if ($LASTEXITCODE -ne 0) { throw 'Private runtime lint failed.' }
    & uv --directory $PrivateWorktree run pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Private runtime tests failed.' }
}

Write-Output "Updated stack:   $newStack"
Write-Output "Updated private: $((& git -C $PrivateWorktree rev-parse HEAD).Trim())"
Write-Output 'Upstream-first rebase and validation completed.'
