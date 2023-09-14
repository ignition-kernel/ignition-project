from zipfile import ZipFile
# from git_semver_tags import Version, highest_tagged_git_version, tag_datetime
import os, sys, re


FILE_ENCODING = 'utf-8'

DIST_EXPORT_FOLDER = './dist'


def unpack_project_export(zip_filename, export_folder=DIST_EXPORT_FOLDER):
    src_file = os.path.abspath('./dist/%s' % (zip_filename,))

    project_scripts_dir = os.path.abspath('./resources/python')
    webdev_scripts_dir = os.path.abspath('./resources/webdev')

    with ZipFile(src_file, 'r') as projzip:
        
        for filepath in projzip.namelist():
            if filepath.endswith('/resource.json'):
                continue

            if 'ignition/script-python/' in filepath and filepath.endswith('/code.py'):
                sub_path = filepath[len('ignition/script-python/'):-len('/code.py')]                
                dst_path = os.path.abspath(os.path.join(project_scripts_dir, sub_path + '.py'))

            elif 'com.inductiveautomation.webdev' in filepath:
                sub_path = filepath[len('com.inductiveautomation.webdev/resources/'):]
                dst_path = os.path.abspath(os.path.join(webdev_scripts_dir, sub_path))
            else:
                continue

            os.makedirs(os.path.dirname(dst_path),exist_ok=True)

            with open(dst_path, 'w', encoding=FILE_ENCODING, newline='\n') as write_file:
                with projzip.open(filepath, 'r') as read_zip:
                    contents = read_zip.read().decode(FILE_ENCODING)
                    write_file.write(contents)



# def latest_export_version(version_filter=None, search_root=DIST_EXPORT_FOLDER):
#     EXPORT_FILENAME_PATTERN = re.compile('(?P<project>.+)_(?P<version>v.+).zip', re.I)

#     desired_version = Version(version_filter)

#     export_bundles = []
#     for filename in os.listdir(search_root):
        
#         matched = EXPORT_FILENAME_PATTERN.match(filename)
        
#         if not matched:
#             continue
        
#         version = Version(matched.groupdict()['version'])
        
#         if not version in desired_version:
#             continue

#         export_bundles.append((version, filename))
        
#     export_bundles.sort(reverse=True)

#     return export_bundles[0][1]



def latest_export(search_root=DIST_EXPORT_FOLDER):
    return sorted([
        filename
        for filename
        in os.listdir(search_root)
        if filename.endswith('.zip')
    ], key=lambda filename: -os.path.getmtime(os.path.join(search_root, filename))
    )[0]



if __name__ == '__main__':

    # if len(sys.argv) > 1:
    #     version_filter = sys.argv[1]
    # else:
    #     version_filter = None


    # if version_filter:
    #     project_export = latest_export_version(version_filter)
    # else:
    #     project_export = latest_export()

    project_export = latest_export()

    print('Unpacking %s' % (project_export,))
    unpack_project_export(project_export)


