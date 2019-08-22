from typing import Set, Any, Dict, List
import collections

import yaml

import data_algebra.table_rep
import data_algebra.pipe
import data_algebra.env


# yaml notes:
#    https://stackoverflow.com/questions/2627555/how-to-deserialize-an-object-with-pyyaml-using-safe-load

# derived from: https://stackoverflow.com/a/16782282/6901725
def represent_ordereddict(dumper, data):
    value = [
        (dumper.represent_data(node_key), dumper.represent_data(node_value))
        for (node_key, node_value) in data.items()
    ]
    return yaml.nodes.MappingNode(u"tag:yaml.org,2002:map", value)


yaml.add_representer(collections.OrderedDict, represent_ordereddict)


class ViewRepresentation(data_algebra.pipe.PipeValue):
    """Structure to represent the columns of a query or a table.
       Abstract base class."""

    column_names: List[str]
    column_set: Set[str]
    column_map: data_algebra.env.SimpleNamespaceDict
    sources: List[Any]  # actually ViewRepresentation

    def __init__(self, column_names, *, sources=None):
        self.column_names = [c for c in column_names]
        for ci in self.column_names:
            if not isinstance(ci, str):
                raise Exception("non-string column name(s)")
        if len(self.column_names) < 1:
            raise Exception("no column names")
        self.column_set = set(self.column_names)
        if not len(self.column_names) == len(self.column_set):
            raise Exception("duplicate column name(s)")
        column_dict = {
            ci: data_algebra.table_rep.ColumnReference(self, ci)
            for ci in self.column_names
        }
        self.column_map = data_algebra.env.SimpleNamespaceDict(**column_dict)
        if sources is None:
            sources = []
        for si in sources:
            if not isinstance(si, ViewRepresentation):
                raise Exception("all sources must be of class ViewRepresentation")
        self.sources = [si for si in sources]
        data_algebra.pipe.PipeValue.__init__(self)

    def collect_representation(self, pipeline=None):
        """convert a data_algebra operator pipeline into a
        simple form for YAML serialization"""
        raise Exception("base method called")

    def __repr__(self):
        return "ViewRepresentation(" + self.column_names.__repr__() + ")"

    def __str__(self):
        return "ViewRepresentation(" + self.column_names.__repr__() + ")"

    # define builders for all non-leaf node types on base class

    def extend(self, ops):
        return ExtendNode(self, ops)


class TableDescription(ViewRepresentation):
    """Describe columns, and qualifiers, of a table.

       If outer namespace is set user values are visible and
       _-side effects can be written back.

       Example:
           from data_algebra.data_ops import *
           import data_algebra.env
           with data_algebra.env.Env(globals()) as env:
               d = TableDescription('d', ['x', 'y'])
           print(_) # should be a SimpleNamespaceDict, not d/ViewRepresentation
           print(d)
    """

    table_name: str
    qualifiers: Dict[str, str]

    def __init__(self, table_name, column_names, *, qualifiers=None):
        ViewRepresentation.__init__(self, column_names=column_names)
        if (table_name is not None) and (not isinstance(table_name, str)):
            raise Exception("table_name must be a string")
        self.table_name = table_name
        self.column_names = column_names.copy()
        if qualifiers is None:
            qualifiers = {}
        if not isinstance(qualifiers, dict):
            raise Exception("qualifiers must be a dictionary")
        self.qualifiers = qualifiers.copy()
        data_algebra.env.maybe_set_underbar(mp0=self.column_map.__dict__)

    def collect_representation(self, pipeline=None):
        if pipeline is None:
            pipeline = []
        od = collections.OrderedDict()
        od["op"] = "TableDescription"
        od["table_name"] = self.table_name
        od["qualifiers"] = self.qualifiers.copy()
        od["column_names"] = self.column_names
        pipeline.insert(0, od)
        return pipeline

    def __repr__(self):
        if len(self.qualifiers) > 0:
            return "Table(" + str(self.qualifiers) + ", " + self.table_name + ")"
        return self.table_name

    def __str__(self):
        if len(self.qualifiers) > 0:
            return "Table(" + str(self.qualifiers) + ", " + self.table_name + ")"
        return self.table_name


class ExtendNode(ViewRepresentation):
    ops: Dict[str, data_algebra.table_rep.Expression]

    def __init__(self, source, ops):
        if not isinstance(source, ViewRepresentation):
            raise Exception("source must be a ViewRepresentation")
        ops = data_algebra.table_rep.check_convert_op_dictionary(
            ops, source.column_map.__dict__
        )
        column_names = source.column_names.copy()
        known_cols = set(column_names)
        for ci in ops.keys():
            if ci not in known_cols:
                column_names = column_names + [ci]
        ViewRepresentation.__init__(self, column_names=column_names, sources=[source])
        self.ops = ops
        data_algebra.env.maybe_set_underbar(mp0=self.column_map.__dict__)

    def collect_representation(self, pipeline=None):
        if pipeline is None:
            pipeline = []
        od = collections.OrderedDict()
        od["op"] = "Extend"
        od["ops"] = {ci: vi.to_python() for (ci, vi) in self.ops.items()}
        pipeline.insert(0, od)
        self.sources[0].collect_representation(pipeline)
        return pipeline

    def __repr__(self):
        return str(self.sources[0]) + " >>\n    " + "Extend(" + str(self.ops) + ")"

    def __str__(self):
        return str(self.sources[0]) + " >>\n    " + "Extend(" + str(self.ops) + ")"


class Extend(data_algebra.pipe.PipeStep):
    """Class to specify adding or altering columns.

       If outer namespace is set user values are visible and
       _-side effects can be written back.

       Examples:
           from data_algebra.data_ops import *
           import data_algebra.env
           with data_algebra.env.Env(locals()) as env:
               q = 4
               x = 2
               var_name = 'y'

               print("first example")
               ops = (
                  TableDescription('d', ['x', 'y']) >>
                     Extend({'z':_.x + _[var_name]/q + _get('x')})
                )
                print(ops)

                print("ex 2")
                ops2 = (
                    TableDescription('d', ['x', 'y']) .
                        extend({'z':'1/q + x'})
                )
                print(ops2)

                print("ex 3")
                ops3 = (
                    TableDescription('d', ['x', 'y']) .
                        extend({'z':'1/q + _.x/_[var_name]', 'f':1, 'g':'"2"', 'h':True})
                )
                print(ops3)

                print("ex 4")
                import data_algebra.pipe

                ops4 = data_algebra.pipe.build_pipeline(
                    TableDescription('d', ['x', 'y']),
                    Extend({'z':'1/_.y + 1/q', 'x':'x+1'})
                )
                print(ops4)

                print("ex 5, columns take precedence over values")
                ops5 = (
                    TableDescription('d', ['q', 'y']) .
                        extend({'z':'1/q + y'})
                )
                print(ops5)

                print("ex 6, forcing values")
                ops6 = (
                    TableDescription('d', ['q', 'y']) .
                        extend({'z':'q/_get("q") + y + _.q'})
                )
                print(ops6)

                p = ops6.collect_representation()
                print(p)
                import yaml
                dmp = yaml.dump(p)
                print(dmp)
                ops6b = data_algebra.data_ops.to_pipeline(yaml.safe_load(dmp))
                print(ops6b)
    """

    def __init__(self, ops):
        data_algebra.pipe.PipeStep.__init__(self, name="Extend")
        self._ops = ops

    def apply(self, other):
        return other.extend(self._ops)


def to_pipeline(obj):
    """De-serialize data_algebra operator pipeline from a collect_representation() form.

       Note: eval() is called to interpret expressions on some nodes, so this
       function is not safe to use on untrusted code.
    """
    if isinstance(obj, dict):
        # a pipe stage
        op = obj["op"]
        # ugly switch statement
        if op == "TableDescription":
            return TableDescription(
                table_name=obj["table_name"],
                column_names=obj["column_names"],
                qualifiers=obj["qualifiers"],
            )
        elif op == "Extend":
            return Extend(ops=obj["ops"])
        else:
            raise Exception("Unexpected op name")
    if isinstance(obj, list):
        # a pipeline, assumed non empty
        res = to_pipeline(obj[0])
        for i in range(1, len(obj)):
            nxt = to_pipeline(obj[i])
            res = res >> nxt
        return res
    raise Exception("unexpected type")
