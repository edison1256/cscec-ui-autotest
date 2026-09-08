param(
    [switch]$SkipGithub,
    [switch]$SkipDevops,
    [string]$GithubRemote = "github",
    [string]$DevopsRemote = "https://devops.cscec.com/osc/irp/irp-ui-autotest.git",
    [string]$ProjectPrefix = "cscec-ui-autotest",
    [string]$SubtreeBranch = "cscec-ui-autotest-only",
    [string]$DevopsBranch = "cscec-ui-autotest-devops",
    [string]$TargetBranch = "master"
)

$ErrorActionPreference = "Stop"

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & git @Args
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Args -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Test-GitBranch {
    param([string]$RepoRoot, [string]$BranchName)
    $branchRef = & git -C $RepoRoot show-ref --verify "refs/heads/$BranchName" 2>$null
    return -not [string]::IsNullOrWhiteSpace($branchRef)
}

$projectDir = Split-Path -Parent $PSScriptRoot
$repoRoot = (& git -C $projectDir rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or -not $repoRoot) {
    throw "Unable to resolve git repository root from $projectDir"
}

$expectedProjectDir = Join-Path $repoRoot $ProjectPrefix
$resolvedProjectDir = (Resolve-Path -LiteralPath $projectDir).Path
$resolvedExpectedProjectDir = (Resolve-Path -LiteralPath $expectedProjectDir).Path
if ($resolvedProjectDir -ne $resolvedExpectedProjectDir) {
    throw "Project directory mismatch. Expected $resolvedExpectedProjectDir, got $resolvedProjectDir"
}

$projectStatus = & git -C $repoRoot -c core.quotePath=false status --short -- $ProjectPrefix
$blockingStatus = $projectStatus | Where-Object {
    $_ -and
    ($_ -notmatch "^\s*M\s+$ProjectPrefix/\.env\.example$")
}
if ($blockingStatus) {
    Write-Host "Project has local changes that are not safe to mirror automatically:"
    $blockingStatus | ForEach-Object { Write-Host $_ }
    throw "Commit or clean project changes before syncing remotes."
}

if (-not $SkipGithub) {
    Write-Host "Pushing $TargetBranch to $GithubRemote..."
    Invoke-Git -C $repoRoot push $GithubRemote $TargetBranch
}

if (-not $SkipDevops) {
    $mirrorDir = Join-Path $repoRoot "$ProjectPrefix-devops-mirror"
    if (Test-Path -LiteralPath $mirrorDir) {
        $mirrorStatus = & git -C $mirrorDir status --short
        if ($LASTEXITCODE -eq 0 -and $mirrorStatus) {
            Write-Host "DevOps mirror worktree has local changes:"
            $mirrorStatus | ForEach-Object { Write-Host $_ }
            throw "Clean $mirrorDir before syncing."
        }
        Invoke-Git -C $repoRoot worktree remove --force $mirrorDir
    }

    if ((Test-GitBranch -RepoRoot $repoRoot -BranchName $SubtreeBranch)) {
        Invoke-Git -C $repoRoot branch -D $SubtreeBranch
    }
    Invoke-Git -C $repoRoot subtree split --prefix=$ProjectPrefix -b $SubtreeBranch

    if ((Test-GitBranch -RepoRoot $repoRoot -BranchName $DevopsBranch)) {
        Invoke-Git -C $repoRoot branch -D $DevopsBranch
    }
    Invoke-Git -C $repoRoot branch $DevopsBranch $SubtreeBranch
    Invoke-Git -C $repoRoot worktree add $mirrorDir $DevopsBranch

    if (Test-Path -LiteralPath (Join-Path $mirrorDir ".github")) {
        Invoke-Git -C $mirrorDir rm -r -- .github
        Invoke-Git -C $mirrorDir commit -m "chore: remove github workflow from devops mirror"
    }

    $forbidden = & git -C $mirrorDir -c core.quotePath=false ls-tree -r --name-only HEAD
    $forbidden = $forbidden | Where-Object {
        $_ -match "^(\.github/|\.agents/|\.workbuddy/|\.claude/|\.playwright-cli/|auth_states/|logs/|reports/|screenshots/|\.env$|scratch|\.idea/|\.venv/|\.pytest_cache/)"
    }
    if ($forbidden) {
        Write-Host "Forbidden files would be pushed to DevOps:"
        $forbidden | ForEach-Object { Write-Host $_ }
        throw "DevOps mirror contains forbidden files."
    }

    Write-Host "Pushing DevOps mirror to $DevopsRemote $TargetBranch..."
    Invoke-Git -C $mirrorDir push $DevopsRemote HEAD:$TargetBranch
}

Write-Host "Remote sync completed."
