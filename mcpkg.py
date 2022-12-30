import requests
import sys
import os
import json
import datetime
import dateutil.parser
import urllib.request
import platform

VERSION = "0.1"
MODRINTH_API_URL = "https://api.modrinth.com/v2"
CURSEFORGE_API_URL = "https://api.curseforge.com/v1"

cfg = json.loads(open("config.json", "r").read())
modrinth_user_agent = cfg['modrinth_user_agent'].format(version=cfg['version'], python_version=platform.python_version())
print(modrinth_user_agent)

def showHelp():
    print("")
    print("query <slug>\tsearch for mod by slug")
    print("install <list>\tdownload mods for the provided modlist")
    exit()

def install(modpack_file_path):
    modpack_file = open(modpack_file_path, "r").read()
    modpack_lines = modpack_file.split("\n")
    
    modpack_folder = modpack_file_path[:-4] if modpack_file_path.endswith(".txt") else modpack_file_path
    os.makedirs(modpack_folder, exist_ok=True)
    
    mc_version = None
    loader = None
    mods = []
    
    for l in modpack_lines:
        l = l.strip()
        if l=='' or l[0]=='#':
            continue
        l = l.split("#")[0].strip()
        if l[0]=='@':
            l = l[1:]
            l_args = l.split("=")
            if len(l_args)==2:
                if l_args[0]=="version": mc_version=l_args[1].strip()
                if l_args[0]=="loader": loader=l_args[1].strip()
        elif l.startswith("https://"):
            l=l[8:]
            if l.startswith("modrinth.com"):
                mods.append({
                    'slug': l.split("/")[2].strip(),
                    'source': 'modrinth'
                })
            elif l.startswith("curseforge.com/minecraft"):
                mods.append({
                    'slug': l.split("/")[3].strip(),
                    'source': 'curseforge'
                })
        else:
            l_args = l.split(":")
            mods.append({
                'slug': l_args[1].strip(),
                'source': l_args[0].strip()
            })
        
    if mc_version is None:
        print("error, mc version is not set")
        return
    if loader is None:
        print("error, loader is not set")
        return
        
    cf_modloadertype = 0
    if loader=="forge": cf_modloadertype=1
    if loader=="fabric": cf_modloadertype=4
    if loader=="quilt": cf_modloadertype=5
        
    print(f"mc version: {mc_version}")
    print(f"loader: {loader}")
    print("resolving dependencies...")
    
    modrinth_incompatible = []
    curseforge_incompatible = []
    skipped = []
    
    i = 0
    while 1:
        if i>=len(mods): break
        if mods[i]['source']=="modrinth":
            chosen_version = None
            if 'modrinth_version_id' in mods[i]:
                r = requests.get(f"{MODRINTH_API_URL}/version/{mods[i]['modrinth_version_id']}", headers = {"User-Agent": modrinth_user_agent})
                if r.status_code != 200:
                    print(f"[error] modrinth: failed to get version '{mods[i]['modrinth_version_id']}' (error {r.status_code})")
                    return
                else:
                    chosen_version = r.json()
            else:
                r = requests.get(f"{MODRINTH_API_URL}/project/{mods[i]['slug']}/version?game_versions=[\"{mc_version}\"]&loaders=[\"{loader}\"]", headers = {"User-Agent": modrinth_user_agent})
                if r.status_code != 200:
                    print(f"[error] modrinth: failed to get '{mods[i]['slug']}' (error {r.status_code})")
                    return
                else:
                    versions = r.json()
                    if len(versions)==0:
                        print(f"[error] modrinth: no versions available for '{mods[i]['slug']}'")
                        #return
                        skipped.append({'name': 'modrinth:'+mods[i]['slug'], 'reason': "no versions available"})
                    else:
                        versions = sorted(versions, key=lambda v: dateutil.parser.isoparse(v['date_published']).timestamp(), reverse=True)
                        chosen_version = versions[0]
            if chosen_version:
                mods[i]['modrinth_version_id'] = chosen_version['id']
                #print(chosen_version)
                print(f"{('*' if 'is_dep' in mods[i] else '')}modrinth: {(mods[i]['slug'] if 'slug' in mods[i] else '')} [{chosen_version['id']}] {chosen_version['name'].strip()} ({chosen_version['version_number']}) ")
                for dep in chosen_version['dependencies']:
                    if dep['dependency_type']=='required':
                        print(f" - {dep['file_name']} ({dep['project_id']}, {dep['version_id']})")
                        dep_mod = {
                            'source': 'modrinth',
                            'is_dep': True,
                        }
                        if dep['version_id']: dep_mod['modrinth_version_id'] = dep['version_id']
                        elif dep['project_id']: dep_mod['slug'] = dep['project_id']
                        else: dep_mod = None
                        if dep_mod: mods.append(dep_mod)
                    elif dep['dependency_type']=='incompatible':
                        modrinth_incompatible.append({
                            'base': chosen_version['id'],
                            'dep': dep['version_id'],
                        })
                files = list(filter(lambda f: f['primary'], chosen_version['files']))
                mods[i]['jar_url'] = files[0]['url']
        elif mods[i]['source']=="curseforge":
            chosen_version = None
            cf_game_id = 432 #curseforge minecraft id
            cf_mod_id = -1
            if 'curseforge_mod_id' in mods[i]:
                cf_mod_id = mods[i]['curseforge_mod_id']
            else:
                r = requests.get(f"{CURSEFORGE_API_URL}/mods/search?gameId={cf_game_id}&slug={mods[i]['slug']}", headers = {"x-api-key": cfg['curseforge_token']})
                cfmods = r.json()['data']
                if len(cfmods)==0:
                    print(f"[error] curseforge: cant find '{mods[i]['slug']}' ")
                    return
                else:
                    cf_mod_id = cfmods[0]['id']
            if cf_mod_id:
                r = requests.get(f"{CURSEFORGE_API_URL}/mods/{cf_mod_id}/files?modLoaderType={cf_modloadertype}&gameVersion={mc_version}", headers = {"x-api-key": cfg['curseforge_token']})
                versions = r.json()['data']
                if len(versions)==0:
                    print(f"[error] curseforge: no versions available for '{cfmods[0]['name']}'")
                    #return
                    skipped.append({'name': 'curseforge:'+cfmods[0]['slug'], 'reason': "no versions available"})
                else:
                    versions = sorted(versions, key=lambda v: dateutil.parser.isoparse(v['fileDate']).timestamp(), reverse=True)
                    chosen_version = versions[0]
            if chosen_version:
                mods[i]['curseforge_mod_id'] = chosen_version['modId']
                print(f"{('*' if 'is_dep' in mods[i] else '')}curseforge: {(mods[i]['slug'] if 'slug' in mods[i] else '')} [{chosen_version['modId']}] {chosen_version['displayName'].strip()} ")
                for dep in chosen_version['dependencies']:
                    if dep['relationType']==3: #RequiredDependency
                        print(f" - {dep['modId']} ")
                        mods.append({
                            'source': 'curseforge',
                            'curseforge_mod_id': dep['modId'],
                            'is_dep': True,
                        })
                    elif dep['relationType']==5: #Incompatible
                        curseforge_incompatible.append({
                            'base': chosen_version['modId'],
                            'dep': dep['modId'],
                        })
                mods[i]['jar_url'] = chosen_version['downloadUrl']
        i += 1 
            
    #compatibility check:
    print("compatibility check...")
    for mod in mods:
        if mod['source']=="modrinth":
            for incompat in modrinth_incompatible:
                if incompat['dep'] == mod['modrinth_version_id']:
                    print(f"modrinth: incompatible versions: {incompat['base']} {incompat['dep']}")
                    a = requests.get(f"{MODRINTH_API_URL}/version/{incompat['base']}", headers = {"User-Agent": modrinth_user_agent}).json()['name']
                    b = requests.get(f"{MODRINTH_API_URL}/version/{incompat['dep']}", headers = {"User-Agent": modrinth_user_agent}).json()['name']
                    print(f"  '{a}' is not compatible with '{b}'")
                    return
    
    jarmap = {}
    for mod in mods:
        key = None
        if 'jar_url' not in mod: continue
        if mod['source']=="modrinth":
            key = f"modrinth:{mod['modrinth_version_id']}"
        elif mod['source']=="curseforge":
            key = f"curseforge:{mod['curseforge_mod_id']}"
        if key and key not in jarmap:
            jarmap[key] = mod['jar_url']
    #install:
    installed = 0
    for jar in jarmap.values():
        print(f"installing {jar}")
        rq = urllib.request.Request(jar)
        rq.add_header("User-Agent", modrinth_user_agent)
        with urllib.request.urlopen(rq) as f:
            #jarname = f.info().get_filename()
            jarname = jar.split("/")[-1]
            with open(os.path.join(modpack_folder, jarname), "wb") as j:
                j.write(f.read())
        installed += 1
        
    print(f"installed: {installed}")
    print(f"skipped: {len(skipped)}")
    for sk in skipped:
        print(f"- '{sk['name']}' reason: {sk['reason']}")
        

def query(mod_name):
    #mc_version = "1.19.3"
    
    print(f"querying {mod_name}")

    #modrinth:
    print("modrinth:")
    #mr_loader = "fabric"
    #r = requests.get(f"{MODRINTH_API_URL}/project/{mod_name}/version?game_versions=[\"{mc_version}\"]&loaders=[\"{mr_loader}\"]", headers = {"User-Agent": modrinth_user_agent})
    r = requests.get(f"{MODRINTH_API_URL}/project/{mod_name}/version", headers = {"User-Agent": modrinth_user_agent})
    if r.status_code!=200:
        print(f"failed to get info from modrinth (error {r.status_code})")
    else:
        versions = r.json()
        #print(json.dumps(versions, indent=2))
        for v in versions:
            print(f"  {v['name'].strip()} [{', '.join(v['game_versions'])}] ({', '.join(v['loaders'])})")

    #curseforge:
    print("curseforge:")
    cf_modloadertype_fabric = 4
    cf_game_id = 432 #curseforge minecraft id
    r = requests.get(f"{CURSEFORGE_API_URL}/mods/search?gameId={cf_game_id}&slug={mod_name}", headers = {"x-api-key": cfg['curseforge_token']})
    mods = r.json()['data']
    if len(mods)==0:
        print("not found on curseforge")
    else:
        cf_mod_id = mods[0]['id']
        #r = requests.get(f"{CURSEFORGE_API_URL}/mods/{cf_mod_id}/files?modLoaderType={cf_modloadertype_fabric}&gameVersion={mc_version}", headers = {"x-api-key": cfg['curseforge_token']})
        r = requests.get(f"{CURSEFORGE_API_URL}/mods/{cf_mod_id}/files", headers = {"x-api-key": cfg['curseforge_token']})
        versions = r.json()['data']
        #print(json.dumps(versions, indent=2))
        if len(versions)==0:
            print("no results from curseforge")
        else:
            for v in versions:
                print(f"  {v['displayName'].strip()} [{', '.join(v['gameVersions'])}]")

print(f"MCPKG {cfg['version']}")
args = sys.argv[1:]
#print(args)
if len(args)>=1:

    if args[0].lower() in ['h', 'help', '-h', '--help', '?', '-?', '/?', '/h', '/help']:
        showHelp()
        
    if len(args)>=2 and args[0]=="query":
        query(args[1].strip().lower())
    if len(args)>=2 and args[0]=="install":
        install(args[1].strip())

else:
    showHelp()