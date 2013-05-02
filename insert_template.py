import os
import shutil
import re
import json
import sublime
import sublime_plugin


class Template:
    def __init__(self, name, template_path):
        self.template_path = template_path
        self.name = name
        self.read_conf()

    def read_conf(self):
        try:
            f = open(os.path.join(self.template_path, 'TEMPLATE.json'), 'r')
            conf = json.loads(f.read() or '{}')
            f.close()
        except:
            conf = {}

        conf_def = {
            'ignore_patterns': ['TEMPLATE.json'],
            'default_path': '$project_path',
            'prompt': 'Insert new name'
        }
        # Ensure conf has default values, so merge the 2 dicts.
        self.conf = dict(conf_def, **conf)
        return conf

    def insert(self, new_name, dest_path):
        real_dest_path = os.path.join(dest_path, new_name)
        ignore = shutil.ignore_patterns(*self.conf['ignore_patterns'])
        shutil.copytree(self.template_path, real_dest_path, ignore=ignore)

        # TODO: other useful tokens?
        tokens = {}
        tokens['__name__'] = new_name

        self.rename_files(real_dest_path, tokens)

    def rename_files(self, path, tokens):
        files = [f for f in os.listdir(path)]
        for f in files:
            f_abs = os.path.join(path, f)
            if os.path.isdir(f_abs):
                self.rename_files(f_abs, tokens)

            name = f
            for token in tokens:
                name = name.replace(token, tokens[token])

            if f != name:
                os.rename(f_abs, os.path.join(path, name))


class Templates:
    def __init__(self):
        plugin_path = os.path.join(sublime.packages_path(), 'sublime-template')
        self.templates_path = os.path.join(plugin_path, 'Templates')
        self.read_list()

    def read_list(self):
        result = []
        files = os.listdir(self.templates_path)
        files = sorted(files)
        for file_name in files:
            if os.path.isdir(os.path.join(self.templates_path, file_name)):
                result.append(file_name)

        self.list = result
        return result

    def get(self, name):
        if name not in self.list:
            return None

        template_path = os.path.join(self.templates_path, name)
        return Template(name, template_path)


class InsertTemplateCommand(sublime_plugin.TextCommand):
    def run(self, edit, path=None):
        self.window = self.view.window()
        self.path = path
        self.manager = Templates()
        self.template = None
        self.new_name = 'noname'
        self.project_path = self.window.folders()[0] or ''

        self.window.show_quick_panel(self.manager.list,
                                     self.on_template_chosen)

    def on_template_chosen(self, index):
        if index is not -1:
            name = self.manager.list[index]
            self.template = self.manager.get(name)
            conf = self.template.conf

            self.window.show_input_panel(conf['prompt'],
                                         '',
                                         self.on_new_name_chosen,
                                         None,
                                         None)

    def on_new_name_chosen(self, new_name):
        self.new_name = new_name

        if self.path is None:
            conf = self.template.conf
            default_path = conf['default_path'].replace('$project_path', self.project_path)

            self.window.show_input_panel('Destination path',
                                         default_path,
                                         self.on_dest_path_chosen,
                                         None,
                                         None)
        else:
            self.insert()

    def on_dest_path_chosen(self, path):
        self.path = path
        self.insert()

    def insert(self):
        result = self.template.insert(self.new_name, self.path)

        # Load main file, which should contain a snippet.
        if 'main' in self.template.conf:
            main = self.template.conf['main'].replace('__name__', self.new_name)
            main_file = os.path.join(self.path, self.new_name, main)

            if os.path.exists(main_file):
                f = open(main_file, 'r')
                main_snippet = f.read()
                f.close()

                main_view = self.window.open_file(main_file)

                def check_loaded():
                    if main_view.is_loading():
                        sublime.set_timeout(check_loaded, 100)
                    else:
                        # select_all is needed to replace content with snippet.
                        main_view.run_command('select_all')
                        main_view.run_command('insert_snippet', {'contents': main_snippet})

                # File loading is async, so it's not possible to run
                # select_all + insert_wrapper immediately after (could cause bugs).
                check_loaded()


class InsertTemplateInPathsCommand(sublime_plugin.WindowCommand):
    def run(self, paths):
        # Call main plugin with custom path.
        self.window.active_view().run_command('insert_template',
                                              {'path': paths[0]})
