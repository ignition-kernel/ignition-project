"""
    Pack up the python scripts for import into Ignition
"""


import os, shutil
import json
import re
from datetime import datetime
from enum import Enum
import hashlib, json, struct

from zipfile import ZipFile

from git_semver_tags import highest_tagged_git_version



class ResourceScopeEnum(Enum):
    A = 7



def filedata(filepath):
    with open(filepath, 'rb') as f:
        return f.read()#.replace('\r\n', '\n')


def get_bytes(value):
    if isinstance(value, bool):
        return bytearray([value])
    if isinstance(value, int):
        return bytearray(struct.pack('!i', value))
    elif isinstance(value, str):
        return bytearray(value, 'utf-8') # or 'latin-1' if it fails?
    elif value is None:
        return bytearray()
    elif isinstance(value, dict):
        json_string = json.dumps(value, sort_keys=True, separators=(',', ':'))
        return get_bytes(json_string)
    else:
        return bytearray(value)



def generate_resource_file(ignition_resource_dir, files,
                           manifest=None, timestamp=None, actor="github", 
                           **overrides):
    """Attempts to generate a signature as well. Totally janky.    
    """
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp[:19])
    elif timestamp is None:
        timestamp = datetime.utcnow()
        
    resource_dict = {
      "scope": "A",
      "version": 1,
      "restricted": False,
      "overridable": True,
      "files": files,
      "attributes": {
        "lastModification": {
          "actor": actor,
          "timestamp": timestamp.isoformat('T', 'seconds')[:19] + 'Z',
        },
      }
    }
    
    resource_dict.update(manifest or {})
    resource_dict.update(overrides)

    manefest_payload = bytearray()
    
    manefest_payload += get_bytes(ResourceScopeEnum[resource_dict['scope']].value)
    manefest_payload += get_bytes(resource_dict.get('documentation'))

    manefest_payload += get_bytes(resource_dict['version'])
    manefest_payload += get_bytes(resource_dict.get('locked', False))
    manefest_payload += get_bytes(resource_dict['restricted'])
    manefest_payload += get_bytes(resource_dict['overridable'])
            
    for filename in sorted(resource_dict['files']):
        # print(os.path.join(ignition_resource_dir, filename))
        manefest_payload += get_bytes(filename)
        manefest_payload += get_bytes(filedata(os.path.join(ignition_resource_dir, filename)))

    assert 'lastModification' in resource_dict['attributes']
    assert set(resource_dict['attributes']['lastModification']).issuperset(set(['actor', 'timestamp']))
    
    for key, value in sorted(resource_dict['attributes'].items()):
        if key == 'lastModificationSignature':
            continue
        manefest_payload += get_bytes(key)
        manefest_payload += get_bytes(value)
            
    resource_dict['attributes']['lastModificationSignature'] = hashlib.sha256(manefest_payload).hexdigest()
        
    with open(os.path.join(ignition_resource_dir, 'resource.json'), 'w') as res_file:
        json.dump(resource_dict, res_file, indent='  ', sort_keys=True)

    return resource_dict


def mirror_into_ignition_project_script_format(src_dir, dst_dir):
    
    src_dir = os.path.abspath(src_dir)
    dst_dir = os.path.abspath(dst_dir)

    shutil.rmtree(dst_dir, ignore_errors=True)

    for root, dirs, files in os.walk(src_dir):
        # skip hidden directories
        for dirname in dirs:
            if dirname.startswith('.'):
                dirs.remove(dirname)
        
        # resource subpath
        sub_path = root[len(src_dir)+1:]
        
        # generate python resources for each
        for filename in files:
            if not filename.endswith('.py'):
                continue
            if re.match(r'__.+__\.py', filename):
                continue
                        
            resource_dir = os.path.join(dst_dir, sub_path, filename[:-3])

            os.makedirs(resource_dir)

            # copy the source code over
            #  BUT! Normalize the line endings first!
            #  _TRUST ME THIS HELPS_
            # Note that we read in one encoding and write back - this ensures no mangling.
            # shutil.copy(os.path.join(root, filename), os.path.join(resource_dir, 'code.py'))
            encoding = 'utf-8' # 'latin-1'
            with open(os.path.join(root, filename), 'r', encoding=encoding) as src_file:
                with open(os.path.join(resource_dir, 'code.py'), 'wb') as dst_file:
                    dst_file.write(src_file.read().replace('\r\n', '\n').encode(encoding))        
            
            _ = generate_resource_file(resource_dir, files=['code.py'])


def mirror_into_ignition_webdev_format(src_dir, dst_dir):
    
    src_dir = os.path.abspath(src_dir)
    dst_dir = os.path.abspath(dst_dir)

    shutil.rmtree(dst_dir, ignore_errors=True)

    for root, dirs, files in os.walk(src_dir):
        # skip hidden directories
        for dirname in dirs:
            if dirname.startswith('.'):
                dirs.remove(dirname)
        
        if not files:
            continue

        # resource subpath
        sub_path = root[len(src_dir)+1:]
        resource_dir = os.path.join(dst_dir, sub_path)
        os.makedirs(resource_dir)

        # copy resources directly
        for filename in files:

            # copy the source code over
            #  BUT! Normalize the line endings first!
            #  _TRUST ME THIS HELPS_
            # Note that we read in one encoding and write back - this ensures no mangling.
            # shutil.copy(os.path.join(root, filename), os.path.join(resource_dir, 'code.py'))
            encoding = 'utf-8' # 'latin-1'
            with open(os.path.join(root, filename), 'r', encoding=encoding) as src_file:
                with open(os.path.join(resource_dir, filename), 'wb') as dst_file:
                    dst_file.write(src_file.read().replace('\r\n', '\n').encode(encoding))        
        
        _ = generate_resource_file(resource_dir, files=files)


def package_project_export(zip_root, semver):

    zip_root = os.path.abspath(zip_root)
    build_root = os.path.abspath(os.path.join(zip_root, '..', 'build'))

    with ZipFile(os.path.join(zip_root, 'Jupyter_Kernel_for_Ignition_%s.zip' % (semver)), 'w') as projzip:
        
        # with open(os.path.join(build_root, 'project.json'), 'rb') as read_file:
        #     with projzip.open('project.json', 'w') as write_zip:
        #         write_zip.write(read_file.read())
        
        ignition_root = os.path.join(build_root, 'ignition')
        
        for root, dirs, files in os.walk(build_root):
            # skip hidden directories
            for dirname in dirs:
                if dirname.startswith('.'):
                    dirs.remove(dirname)

            sub_path = root[len(build_root)+1:]
            
            for filename in files:
                
                with open(os.path.join(root, filename), 'rb') as read_file:
                    with projzip.open(os.path.join(sub_path, filename), 'w') as write_zip:
                        write_zip.write(read_file.read())



if __name__ == '__main__':

    mirror_into_ignition_project_script_format('./resources/python', './build/ignition/script-python')
    mirror_into_ignition_webdev_format('./resources/webdev', './build/com.inductiveautomation.webdev/resources')

    package_project_export('./dist/', 'v' + str(highest_tagged_git_version('./')))
