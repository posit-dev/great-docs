from __future__ import annotations

import inspect
import logging
import warnings
from fnmatch import fnmatchcase
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from great_docs._renderer import layout
from great_docs._renderer._griffe_compat import (
    GriffeLoader,
    LinesCollection,
    ModulesCollection,
    Parser,
    parse,
)
from great_docs._renderer._griffe_compat import dataclasses as dc
from great_docs._renderer.inventory import convert_inventory, create_inventory
from great_docs._renderer.pandoc.blocks import Blocks, Header
from great_docs._renderer.pandoc.components import Attr
from great_docs._renderer.parsers import get_parser_defaults
from great_docs._renderer.renderer import Renderer

_log = logging.getLogger(__name__)


# Docstring loading / parsing =================================================


def parse_function(module: str, func_name: str):
    griffe = GriffeLoader()
    mod = griffe.load(module)

    f_data = mod.functions[func_name]

    return parse(f_data.docstring, Parser.numpy)


def get_function(module: str, func_name: str, parser: str = "numpy") -> dc.Object:
    """Fetch a function.

    Parameters
    ----------
    module: str
        A module name.
    func_name: str
        A function name.
    parser: str
        A docstring parser to use.

    """
    griffe = GriffeLoader(
        docstring_parser=Parser(parser), docstring_options=get_parser_defaults(parser)
    )
    mod = griffe.load(module)

    f_data = mod.functions[func_name]

    return f_data


def get_object(
    path: str,
    object_name: "str | None" = None,
    parser: str = "numpy",
    load_aliases=True,
    dynamic=False,
    loader: None | GriffeLoader = None,
) -> dc.Object:
    """Fetch a griffe object.

    Parameters
    ----------
    path: str
        An import path to the object. This should have the form `path.to.module:object`.
        For example, `my_package:get_object` or `my_package:MyClass.render`.
    object_name: str
        (Deprecated). A function name.
    parser: str
        A docstring parser to use.
    load_aliases: bool
        For aliases that were imported from other modules, should we load that module?
    dynamic: bool
        Whether to dynamically import object. Useful if docstring is not hard-coded,
        but was set on object by running python code.

    """

    if object_name is not None:
        warnings.warn("object_name argument is deprecated in get_object", DeprecationWarning)

        path = f"{path}:{object_name}"

    if loader is None:
        loader = GriffeLoader(
            docstring_parser=Parser(parser),
            docstring_options=get_parser_defaults(parser),
            modules_collection=ModulesCollection(),
            lines_collection=LinesCollection(),
        )

    try:
        module, object_path = path.split(":", 1)
    except ValueError:
        module, object_path = path, None

    # load the module if it hasn't been already.
    root_mod = module.split(".", 1)[0]
    if root_mod not in loader.modules_collection:
        loader.load(module)

    # griffe uses only periods for the path
    griffe_path = f"{module}.{object_path}" if object_path else module

    # Case 1: dynamic loading
    if dynamic:
        if isinstance(dynamic, str):
            return dynamic_alias(path, target=dynamic, loader=loader)

        return dynamic_alias(path, loader=loader)

    # Case 2: static loading an object
    f_parent = loader.modules_collection[griffe_path.rsplit(".", 1)[0]]
    f_data = loader.modules_collection[griffe_path]

    if isinstance(f_parent, dc.Alias) and isinstance(f_data, (dc.Function, dc.Attribute)):
        f_data = dc.Alias(f_data.name, f_data, parent=f_parent)

    if isinstance(f_data, dc.Alias) and load_aliases:
        target_mod = f_data.target_path.split(".")[0]
        if target_mod != module:
            loader.load(target_mod)

    return f_data


def _resolve_target(obj: dc.Alias):
    target = obj.target

    count = 0
    while isinstance(target, dc.Alias):
        count += 1
        if count > 100:
            raise ValueError("Attempted to resolve target, but may be infinitely recursing?")

        target = target.target

    return target


def replace_docstring(obj: dc.Object | dc.Alias, f=None):
    """Replace (in place) a docstring for a griffe object.

    Parameters
    ----------
    obj:
        Object to replace the docstring of.
    f:
        The python object whose docstring to use in the replacement. If not
        specified, then attempt to import obj and use its docstring.

    """
    import importlib

    if isinstance(obj, dc.Alias):
        obj = _resolve_target(obj)

    if isinstance(obj, dc.Class):
        for child_obj in obj.members.values():
            replace_docstring(child_obj)

    if f is None:
        mod = importlib.import_module(obj.module.canonical_path)

        if isinstance(obj.parent, dc.Class):
            parent_obj = getattr(mod, obj.parent.name)

            try:
                f = getattr(parent_obj, obj.name)
            except AttributeError:
                return
        else:
            f = getattr(mod, obj.name)

    if f.__doc__ is None:
        return

    old = obj.docstring
    new = dc.Docstring(
        value=f.__doc__,
        lineno=getattr(old, "lineno", None),
        endlineno=getattr(old, "endlineno", None),
        parent=getattr(old, "parent", None),
        parser=getattr(old, "parser", None),
        parser_options=getattr(old, "parser_options", None),
    )

    obj.docstring = new


def dynamic_alias(path: str, target: "str | None" = None, loader=None) -> dc.Object | dc.Alias:
    """Return an Alias, using a dynamic import to find the target.

    Parameters
    ----------
    path:
        Full path to the object. E.g. `my_package.get_object`.
    target:
        Optional path to ultimate Alias target. By default, this is inferred
        using the __module__ attribute of the imported object.

    """
    import importlib

    try:
        mod_name, object_path = path.split(":", 1)
    except ValueError:
        mod_name, object_path = path, None

    mod = importlib.import_module(mod_name)

    if object_path is None:
        attr = mod
        canonical_path = mod.__name__

    else:
        splits = object_path.split(".")

        canonical_path = None
        crnt_part = mod
        for ii, attr_name in enumerate(splits):
            try:
                _qualname = ".".join(splits[ii:])
                new_canonical_path = _canonical_path(crnt_part, _qualname)
            except AttributeError:
                new_canonical_path = None

            if new_canonical_path is not None:
                canonical_path = new_canonical_path

            try:
                crnt_part = getattr(crnt_part, attr_name)
            except AttributeError:
                if canonical_path:
                    try:
                        obj = get_object(canonical_path, loader=loader)
                        if _is_valueless(obj):
                            return obj
                    except Exception as e:
                        raise e

                raise AttributeError(f"No attribute named `{attr_name}` in the path `{path}`.")

        try:
            _qualname = ""
            new_canonical_path = _canonical_path(crnt_part, _qualname)
        except AttributeError:
            new_canonical_path = None

        if new_canonical_path is not None:
            canonical_path = new_canonical_path

        if canonical_path is None:
            raise ValueError(f"Cannot find canonical path for `{path}`")

        attr = crnt_part

    if target:
        obj = get_object(target, loader=loader)
    else:
        obj = get_object(canonical_path, loader=loader)

    replace_docstring(obj, attr)

    if obj.canonical_path == path.replace(":", "."):
        return obj
    else:
        if object_path:
            if "." in object_path:
                prev_member = object_path.rsplit(".", 1)[0]
                parent_path = f"{mod_name}:{prev_member}"
            else:
                parent_path = mod_name
        else:
            parent_path = mod_name.rsplit(".", 1)[0]

        parent = get_object(parent_path, loader=loader, dynamic=True)
        return dc.Alias(attr_name, obj, parent=parent)


def _canonical_path(crnt_part: object, qualname: str):
    suffix = (":" + qualname) if qualname else ""
    if not isinstance(crnt_part, ModuleType):
        if inspect.isclass(crnt_part) or inspect.isfunction(crnt_part):
            _mod = getattr(crnt_part, "__module__", None)

            if _mod is None:
                return None
            else:
                qual_parts = [] if not qualname else qualname.split(".")
                return _mod + ":" + ".".join([crnt_part.__qualname__, *qual_parts])
        elif isinstance(crnt_part, ModuleType):
            return crnt_part.__name__ + suffix
        else:
            return None
    else:
        return crnt_part.__name__ + suffix


def _is_valueless(obj: dc.Object):
    if isinstance(obj, dc.Attribute):
        if obj.labels.union({"class-attribute", "module-attribute"}) and obj.value is None:
            return True
        elif "instance-attribute" in obj.labels:
            return True

    return False


def _insert_contents(
    x: dict | list,
    contents: list,
    sentinel: str = "{{ contents }}",
):
    """Splice `contents` into a list."""
    if isinstance(x, dict):
        for value in x.values():
            if _insert_contents(value, contents):
                return True
    elif isinstance(x, list):
        for i, item in enumerate(x):
            if item == sentinel:
                x[i : i + 1] = contents  # noqa: E203
                return True
            elif _insert_contents(item, contents):
                return True
    return False


# Builder =====================================================================


class Builder:
    """Base class for building API docs.

    Parameters
    ----------
    package: str
        The name of the package.
    sections:
        A list of sections, with items to document.
    version:
        The package version.
    dir:
        Name of API directory.
    title:
        Title of the API index page.
    renderer:
        The renderer used to convert docstrings (e.g. to markdown).
    options:
        Default options to set for all pieces of content.
    out_index:
        The output path of the index file.
    sidebar:
        The output path for a sidebar yaml config.
    rewrite_all_pages:
        Whether to rewrite all rendered doc pages, or only those with changes.
    source_dir:
        A directory where source files to be documented live.
    dynamic:
        Whether to dynamically load all python objects.
    render_interlinks:
        Whether to render interlinks syntax inside documented objects.
    parser:
        Docstring parser to use. One of "google", "sphinx", "numpy".

    """

    style: str
    _registry: "dict[str, Builder]" = {}

    out_inventory: str = "objects.json"
    out_index: str = "index.qmd"
    out_page_suffix = ".qmd"

    package: str
    version: "str | None"
    dir: str
    title: str

    renderer: Renderer
    items: list[layout.Item]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if hasattr(cls, "style") and cls.style in cls._registry:
            raise KeyError(f"A builder for style {cls.style} already exists")

        if hasattr(cls, "style"):
            cls._registry[cls.style] = cls

    def __init__(
        self,
        package: str,
        sections: "list[Any]" = tuple(),
        options: "dict | None" = None,
        version: "str | None" = None,
        dir: str = "reference",
        title: str = "Function reference",
        renderer: "dict | Renderer | str" = "markdown",
        out_index: str = None,
        sidebar: "str | dict[str, Any] | None" = None,
        css: "str | None" = None,
        rewrite_all_pages=False,
        source_dir: "str | None" = None,
        dynamic: bool | None = None,
        parser="numpy",
        render_interlinks: bool = False,
        _fast_inventory=False,
    ):
        self.layout = self.load_layout(sections=sections, package=package, options=options)

        self.package = package
        self.version = None
        self.dir = dir
        self.title = title

        if isinstance(sidebar, str):
            sidebar = {"file": sidebar}
        elif isinstance(sidebar, dict) and "file" not in sidebar:
            sidebar["file"] = "_api-reference-sidebar.yml"
        self.sidebar: "dict[str, Any] | None" = sidebar

        self.css = css
        self.parser = parser

        self.renderer = Renderer.from_config(renderer)
        if render_interlinks:
            self.renderer.render_interlinks = render_interlinks

        if out_index is not None:
            self.out_index = out_index

        self.rewrite_all_pages = rewrite_all_pages
        self.source_dir = str(Path(source_dir).absolute()) if source_dir else None
        self.dynamic = dynamic

        self._fast_inventory = _fast_inventory

    def load_layout(self, sections: dict, package: str, options=None):
        try:
            return layout.Layout(sections=sections, package=package, options=options)
        except (ValueError, TypeError) as e:
            raise ValueError(str(e)) from None

    # building ----------------------------------------------------------------

    def build(self, filter: str = "*"):
        """Build index page, inventory, and individual doc pages."""

        from great_docs._renderer.blueprint import blueprint as _blueprint
        from great_docs._renderer.collect import collect as _collect

        if self.source_dir:
            import sys

            sys.path.append(self.source_dir)

        _log.info("Generating blueprint.")
        bp = _blueprint(self.layout, dynamic=self.dynamic, parser=self.parser)

        _log.info("Collecting pages and inventory items.")
        pages, self.items = _collect(bp, base_dir=self.dir)

        _log.info("Writing index")
        self.write_index(bp)

        _log.info("Writing docs pages")
        self.write_doc_pages(pages, filter)
        self.renderer._pages_written(self)

        _log.info("Creating inventory file")
        inv = self.create_inventory(self.items)
        convert_inventory(inv, self.out_inventory)

        if self.sidebar:
            _log.info(f"Writing sidebar yaml to {self.sidebar['file']}")
            self.write_sidebar(bp)

    def write_index(self, blueprint_layout: layout.Layout):
        """Write API index page."""

        _log.info("Summarizing docs for index page.")
        content = self.renderer.summarize(blueprint_layout)
        _log.info(f"Writing index to directory: {self.dir}")

        final = str(Blocks([Header(1, self.title, Attr(classes=["doc", "doc-index"])), content]))

        p_index = Path(self.dir) / self.out_index
        p_index.parent.mkdir(exist_ok=True, parents=True)
        p_index.write_text(final)

        return str(p_index)

    def write_doc_pages(self, pages, filter: str):
        """Write individual function documentation pages."""

        for page in pages:
            _log.info(f"Rendering {page.path}")
            rendered = self.renderer.render(page)
            html_path = Path(self.dir) / (page.path + self.out_page_suffix)
            html_path.parent.mkdir(exist_ok=True, parents=True)

            if filter != "*":
                is_match = fnmatchcase(page.path, filter)
                if is_match:
                    _log.info("Matched filter")
                else:
                    _log.info("Skipping write (no filter match)")
                    continue

            if (
                self.rewrite_all_pages
                or (not html_path.exists())
                or (html_path.read_text() != rendered)
            ):
                _log.info(f"Writing: {page.path}")
                html_path.write_text(rendered)
            else:
                _log.info("Skipping write (content unchanged)")

    def create_inventory(self, items):
        """Generate inventory object."""

        _log.info("Creating inventory")
        version = "0.0.9999" if self.version is None else self.version
        inventory = create_inventory(self.package, version, items)

        return inventory

    def _generate_sidebar(self, blueprint_layout: layout.Layout, options: "dict | None" = None):
        contents = [f"{self.dir}/index{self.out_page_suffix}"]
        in_subsection = False
        crnt_entry = {}
        for section in blueprint_layout.sections:
            if section.title:
                if crnt_entry:
                    contents.append(crnt_entry)

                in_subsection = False
                crnt_entry = {"section": section.title, "contents": []}
            elif section.subtitle:
                in_subsection = True

            links = []
            for entry in section.contents:
                links.extend(self._page_to_links(entry))

            if in_subsection:
                sub_entry = {"section": section.subtitle, "contents": links}
                crnt_entry["contents"].append(sub_entry)
            else:
                crnt_entry["contents"].extend(links)

        if crnt_entry:
            contents.append(crnt_entry)

        if self.sidebar is None:
            sidebar = {}
        else:
            sidebar = {k: v for k, v in self.sidebar.items() if k != "file"}

        if "id" not in sidebar:
            sidebar["id"] = self.dir

        if "contents" not in sidebar:
            sidebar["contents"] = contents
        else:
            if not isinstance(sidebar["contents"], list):
                raise TypeError("`sidebar.contents` must be a list")

            if not _insert_contents(sidebar["contents"], contents):
                sidebar["contents"].extend(contents)

        entries = [sidebar, {"id": "dummy-sidebar"}]
        return {"website": {"sidebar": entries}}

    def write_sidebar(self, blueprint_layout: layout.Layout):
        """Write a yaml config file for API sidebar."""

        d_sidebar = self._generate_sidebar(blueprint_layout)
        yaml.dump(d_sidebar, open(self.sidebar["file"], "w"))

    def _page_to_links(self, el: layout.Page) -> list[str]:
        return [f"{self.dir}/{el.path}{self.out_page_suffix}"]

    # constructors ----

    @classmethod
    def from_quarto_config(cls, quarto_cfg: "str | dict"):
        """Construct a Builder from a configuration object (or yaml file)."""

        if isinstance(quarto_cfg, str):
            import yaml

            quarto_cfg = yaml.safe_load(open(quarto_cfg))

        cfg = quarto_cfg.get("api-reference") or quarto_cfg.get("quartodoc")
        if cfg is None:
            raise KeyError("No `api-reference:` section found in your _quarto.yml.")
        style = cfg.get("style", "pkgdown")
        cls_builder = cls._registry[style]

        _fast_inventory = quarto_cfg.get("interlinks", {}).get("fast", False)

        return cls_builder(
            **{k: v for k, v in cfg.items() if k != "style"},
            _fast_inventory=_fast_inventory,
        )


class BuilderPkgdown(Builder):
    """Build an API in R pkgdown style."""

    style = "pkgdown"


class BuilderSinglePage(Builder):
    """Build an API with all docs embedded on a single page."""

    style = "single-page"

    def load_layout(self, *args, **kwargs):
        el = super().load_layout(*args, **kwargs)

        el.sections = [layout.Page(path=self.out_index, contents=el.sections)]

        return el

    def write_index(self, *args, **kwargs):
        pass
