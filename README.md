# mcpkg

## about
mcpkg ist a python utility to download minecraft mods from a file list to a folder  
supports downloading from modrinth.com and curseforge.com

## setup
* clone this repo  
* copy `config.example.json` to `config.json`
* create a curseforge api account. generate a key to access their api, and paste it to the config at `curseforge_token`

## usage
cd to the cloned folder or add it to path  
run `mkpkg help` for help  
`mkpkg install <path/to/modlist.txt>` will install mods from that list into a folder with the same name

## modlist format

\# comments lines  
@ adds a filter directive. format: `@name=value` where name is the directive and value its value.  
supported directives:
* `version` specifies the targeted minecraft version
* `loader` specifies the targeted loader. possible values are `fabric`, `forge`

view the mods.example.txt file for an example

## todo
* more filters
  * minVersion
  * maxVersion
  * installDependencies (none, required, optional)
  * ignoreIncompatibilities