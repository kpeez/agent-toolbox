#!/usr/bin/env nu
# Copy the complete sibling skill set into an explicitly chosen project.
# Refuse every existing skill name, including symlinks. No global default.

def main [project: path] {
    let target = ($project | path expand)
    if ($target | path type) != "dir" {
        error make {msg: "The target must be an existing project directory."}
    }
    let source = ($env.FILE_PWD | path join ".." "skills" | path expand)
    let names = [learn learn-genetic learn-refute learn-feynman learn-worked-example learn-quiz learn-review learn-transfer]
    for name in $names {
        if not ($source | path join $name "SKILL.md" | path exists) {
            error make {msg: $"Incomplete Uni bundle: missing ($name)/SKILL.md."}
        }
    }
    let agent_root = ($target | path join ".agents")
    let agent_root_type = ($agent_root | path type | default "missing")
    if $agent_root_type != "missing" and $agent_root_type != "dir" {
        error make {msg: "The project's .agents path must be a directory, not a file or symlink."}
    }
    let destination = ($agent_root | path join "skills")
    let destination_type = ($destination | path type | default "missing")
    if $destination_type != "missing" and $destination_type != "dir" {
        error make {msg: "The project's .agents/skills path must be a directory, not a file or symlink."}
    }
    if $destination_type == "dir" {
        let existing = (ls -a $destination | get name | path basename)
        let collisions = ($names | where {|name| $name in $existing })
        if not ($collisions | is-empty) {
            error make {msg: $"Refusing to overwrite existing skills: ($collisions | str join ', ')."}
        }
    }
    mkdir $destination
    for name in $names {
        cp --recursive --no-clobber ($source | path join $name) $destination
    }
    print $"Copied all eight Uni skills to ($destination). Start Codex in this project; restart if the skills do not appear."
}
