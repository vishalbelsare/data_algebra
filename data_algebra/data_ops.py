from typing import Set, Any, Dict, List
import collections

import yaml

import data_algebra.table_rep
import data_algebra.pipe
import data_algebra.env
import data_algebra.pending_eval


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
        data_algebra.env.maybe_set_underbar(mp0=self.column_map.__dict__)

    def _collect_representation(self, pipeline=None):
        """implementation pf _collect_representation representation with tail-recursion eliminated eval
        subclasses should override _collect_representation().  Users should call _collect_representation().
        """
        raise Exception("base method called")

    def collect_representation(self, pipeline=None):
        """convert a data_algebra operator pipeline into a
        simple form for YAML serialization"""
        f = data_algebra.pending_eval.tail_version(self._collect_representation)
        return f(pipeline=pipeline)

    def __repr__(self):
        return "ViewRepresentation(" + self.column_names.__repr__() + ")"

    def __str__(self):
        return "ViewRepresentation(" + self.column_names.__repr__() + ")"

    # define builders for all non-leaf node types on base class

    def extend(self, ops):
        return ExtendNode(source=self, ops=ops)

    def natural_join(self, b, *, by, jointype):
        return NaturalJoinNode(a=self, b=b, by=by, jointype=jointype)


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

    def _collect_representation(self, pipeline=None):
        if pipeline is None:
            pipeline = []
        od = collections.OrderedDict()
        od["op"] = "TableDescription"
        od["table_name"] = self.table_name
        od["qualifiers"] = self.qualifiers.copy()
        od["column_names"] = self.column_names
        pipeline.insert(0, od)
        return pipeline

    def key(self):
        qstr = ''
        if len(self.qualifiers) > 0:
            keys = [k for k in self.qualifiers.keys()]
            keys.sort()
            qstr = '{'
            for k in keys:
                qstr = qstr + '(' + k + ', ' + str(self.qualifiers[k]) + ')'
            qstr = qstr + '}.'
        return qstr + self.table_name

    def __repr__(self):
         return self.key()

    def __str__(self):
        return self.key()

# TODO: add get all tables in a pipleline and confirm columns are functions of table.key()

class ExtendNode(ViewRepresentation):
    ops: Dict[str, data_algebra.table_rep.Expression]

    def __init__(self, source, ops):
        ops = data_algebra.table_rep.check_convert_op_dictionary(
            ops, source.column_map.__dict__
        )
        column_names = source.column_names.copy()
        known_cols = set(column_names)
        for ci in ops.keys():
            if ci not in known_cols:
                column_names.append(ci)
        ViewRepresentation.__init__(self, column_names=column_names, sources=[source])
        self.ops = ops

    def _collect_representation(self, pipeline=None):
        if pipeline is None:
            pipeline = []
        od = collections.OrderedDict()
        od["op"] = "Extend"
        od["ops"] = {ci: vi.to_python() for (ci, vi) in self.ops.items()}
        pipeline.insert(0, od)
        return data_algebra.pending_eval.tail_call(self.sources[0]._collect_representation)(pipeline=pipeline)

    def __repr__(self):
        return str(self.sources[0]) + " >>\n    " + "Extend(" + str(self.ops) + ")"

    def __str__(self):
        return str(self.sources[0]) + " >>\n    " + "Extend(" + str(self.ops) + ")"


class Extend(data_algebra.pipe.PipeStep):
    """Class to specify adding or altering columns.

       If outer namespace is set user values are visible and
       _-side effects can be written back.

       Example:
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
    """

    ops: Dict[str, data_algebra.table_rep.Expression]

    def __init__(self, ops):
        data_algebra.pipe.PipeStep.__init__(self, name="Extend")
        self._ops = ops

    def apply(self, other):
        return other.extend(self._ops)


class NaturalJoinNode(ViewRepresentation):
    _by: List[str]
    _jointype: str

    def __init__(self, a, b,
                 *,
                 by = None,
                 jointype = 'INNER'):
        sources = [a, b]
        column_names = sources[0].column_names.copy()
        for ci in sources[1].column_names:
            if ci not in sources[0].column_set:
                column_names.append(ci)
        missing0 = set(by) - sources[0].column_set
        missing1 = set(by) - sources[1].column_set
        if (len(missing0)>0) or (len(missing1)>0):
            raise Exception("all by-columns must be in both tables")
        self._by = by
        self._jointype = jointype
        ViewRepresentation.__init__(self, column_names=column_names, sources=sources)

    def _collect_representation(self, pipeline=None):
        if pipeline is None:
            pipeline = []
        od = collections.OrderedDict()
        od["op"] = "NaturalJoin"
        od["by"] = self._by
        od["jointype"] = self._jointype
        od["b"] = self.sources[1].collect_representation()
        pipeline.insert(0, od)
        return data_algebra.pending_eval.tail_call(self.sources[0]._collect_representation)(pipeline=pipeline)

    def __repr__(self):
        return str(self.sources[0]) + " >>\n    " + "NaturalJoin(b=" + str(self.sources[1]) + ", by=" + str(self._by) + ", jointype=" + self._jointype + ")"

    def __str__(self):
        return str(self.sources[0]) + " >>\n    " + "NaturalJoin(b=" + str(self.sources[1]) + ", by=" + str(self._by) + ", jointype=" + self._jointype + ")"


class NaturalJoin(data_algebra.pipe.PipeStep):
    _by: List[str]
    _jointype: str
    _b: ViewRepresentation

    def __init__(self,
                 *,
                 b = None,
                 by = None,
                 jointype = 'INNER'):
        if not isinstance(b, ViewRepresentation):
            raise Exception("b should be a ViewRepresentation")
        missing1 = set(by) - b.column_set
        if len(missing1) > 0:
            raise Exception("all by-columns must be in b-table")
        data_algebra.pipe.PipeStep.__init__(self, name="NaturalJoin")
        self._by = by
        self._jointype = jointype
        self._b = b

    def apply(self, other):
        return other.natural_join(b = self._b,
                                  by = self._by,
                                  jointype = self._jointype)


def to_pipeline(obj):
    """De-serialize data_algebra operator pipeline from a collect_representation() form.

       Note: eval() is called to interpret expressions on some nodes, so this
       function is not safe to use on untrusted code (though a somewhat restricted
       version of eval() is used to try and catch some issues).
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
        elif op == "NaturalJoin":
            return NaturalJoin(by=obj["by"],
                               jointype=obj["jointype"],
                               b=to_pipeline(obj["b"]))
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
