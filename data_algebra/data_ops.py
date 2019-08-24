from typing import Set, Any, Dict, List
import collections

import data_algebra.expr_rep
import data_algebra.pipe
import data_algebra.env
import data_algebra.pending_eval


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
            ci: data_algebra.expr_rep.ColumnReference(self, ci)
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

    # characterization

    def get_tables_implementation(self):
        tables = []
        for s in self.sources:
            tables = tables + s.get_tables_implementation()
        return tables

    def get_tables(self):
        """get a dictionry of all tables used in an operator DAG, raise an exception if the values are not consistent"""
        tables = self.get_tables_implementation()
        # check that table columns are a function of table keys (i.e. equivalent definitions being used everywhere)
        examples = {ti.key:ti for ti in tables}
        for ti in tables:
            ei = examples[ti.key]
            cseta = set(ei.column_names)
            csetb = set(ti.column_names)
            if not cseta == csetb:
                raise Exception("Twp tables with key " + ti.key + " have different column sets.")
        return examples

    # collect as simple structures for YAML I/O and other generic tasks

    def collect_representation_implementation(self, pipeline=None):
        raise Exception("base method called")

    def collect_representation(self, pipeline=None):
        self.get_tables()  # for table consistency check/raise
        return self.collect_representation_implementation(pipeline=pipeline)

    # printing

    def format_ops_implementation(self, indent=0):
        return "ViewRepresentation(" + self.column_names.__repr__() + ")"

    def format_ops(self, indent=0):
        self.get_tables()  # for table consistency check/raise
        return self.format_ops_implementation(indent=indent)

    def __repr__(self):
        return self.format_ops()

    def __str__(self):
        return self.format_ops()

    # query generation

    def to_sql_implementation(self, db_model, *, using=None, temp_id_source=None):
        raise Exception("base method called")

    def to_sql(self, db_model, *, using=None, temp_id_source=None):
        """

        :param db_model: data_algebra_db_model.DBModel
        :param using: set of columns used from this view, None implies all columns
        :param temp_id_source: list a single integer to generate temp-ids for sub-queries
        :return:
        """
        self.get_tables()  # for table consistency check/raise
        return self.to_sql_implementation(db_model=db_model, using=using, temp_id_source=temp_id_source)

    # define builders for all non-leaf node types on base class

    def extend(self, ops, *, partition_by=None, order_by=None, reverse=None):
        return ExtendNode(
            source=self,
            ops=ops,
            partition_by=partition_by,
            order_by=order_by,
            reverse=reverse,
        )

    def natural_join(self, b, *, by=None, jointype="INNER"):
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
    key: str

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
        key = ""
        if len(self.qualifiers) > 0:
            keys = [k for k in self.qualifiers.keys()]
            keys.sort()
            key = "{"
            for k in keys:
                key = key + "(" + k + ", " + str(self.qualifiers[k]) + ")"
            key = key + "}."
        self.key = key + self.table_name

    def collect_representation_implementation(self, pipeline=None):
        if pipeline is None:
            pipeline = []
        od = collections.OrderedDict()
        od["op"] = "TableDescription"
        od["table_name"] = self.table_name
        od["qualifiers"] = self.qualifiers.copy()
        od["column_names"] = self.column_names
        od["key"] = self.key
        pipeline.insert(0, od)
        return pipeline

    def format_ops_implementation(self, indent=0):
        nc = min(len(self.column_names), 10)
        ellipis_str = ""
        if nc < len(self.column_names):
            ellipis_str = ", ..."
        s = (
            "Table("
            + self.key
            + "; "
            + ", ".join([self.column_names[i] for i in range(nc)])
            + ellipis_str
            + ")"
        )
        return s

    def get_tables_implementation(self):
        return [self]

    def to_sql_implementation(self, db_model, *, using=None, temp_id_source=None):
        return db_model.table_def_to_sql(
            self, using=using
        )

    # comparable to other table descriptions
    def __lt__(self, other):
        if not isinstance(other, TableDescription):
            return True
        return self.key.__lt__(other.key)

    def __eq__(self, other):
        if not isinstance(other, TableDescription):
            return False
        return self.key.__eq__(other.key)

    def __hash__(self):
        return self.key.__hash__()


class ExtendNode(ViewRepresentation):
    ops: Dict[str, data_algebra.expr_rep.Expression]

    def __init__(self, source, ops, *, partition_by=None, order_by=None, reverse=None):
        ops = data_algebra.expr_rep.check_convert_op_dictionary(
            ops, source.column_map.__dict__
        )
        if len(ops) < 1:
            raise Exception("no ops")
        self.ops = ops
        if partition_by is None:
            partition_by = []
        if isinstance(partition_by, str):
            partition_by = [partition_by]
        self.partition_by = partition_by
        if order_by is None:
            order_by = []
        if isinstance(order_by, str):
            order_by = [order_by]
        self.order_by = order_by
        if reverse is None:
            reverse = []
        if isinstance(reverse, str):
            reverse = [reverse]
        self.reverse = reverse
        column_names = source.column_names.copy()
        consumed_cols = set()
        for (k, o) in ops.items():
            o.get_column_names(consumed_cols)
        unknown_cols = consumed_cols - source.column_set
        if len(unknown_cols) > 0:
            raise Exception("referered to unknown columns: " + str(unknown_cols))
        known_cols = set(column_names)
        for ci in ops.keys():
            if ci not in known_cols:
                column_names.append(ci)
        if len(partition_by) != len(set(partition_by)):
            raise Exception("Duplicate name in partition_by")
        if len(order_by) != len(set(order_by)):
            raise Exception("Duplicate name in order_by")
        if len(reverse) != len(set(reverse)):
            raise Exception("Duplicate name in reverse")
        unknown = set(partition_by) - known_cols
        if len(unknown) > 0:
            raise Exception("unknown partition_by columns: " + str(unknown))
        unknown = set(order_by) - known_cols
        if len(unknown) > 0:
            raise Exception("unknown order_by columns: " + str(unknown))
        unknown = set(reverse) - set(order_by)
        if len(unknown) > 0:
            raise Exception("reverse columns not in order_by: " + str(unknown))
        ViewRepresentation.__init__(self, column_names=column_names, sources=[source])

    def collect_representation_implementation(self, pipeline=None):
        if pipeline is None:
            pipeline = []
        od = collections.OrderedDict()
        od["op"] = "Extend"
        od["ops"] = {ci: vi.to_python() for (ci, vi) in self.ops.items()}
        od["partition_by"] = self.partition_by
        od["order_by"] = self.order_by
        od["reverse"] = self.reverse
        pipeline.insert(0, od)
        return self.sources[0].collect_representation_implementation(pipeline=pipeline)

    def format_ops_implementation(self, indent=0):
        s = (
            self.sources[0].format_ops_implementation(indent=indent)
            + " .\n"
            + " " * (indent + 3)
            + "extend("
            + str(self.ops)
        )
        if len(self.partition_by) > 0:
            s = s + ", partition_by:" + str(self.partition_by)
        if len(self.order_by) > 0:
            s = s + ", order_by:" + str(self.order_by)
        if len(self.reverse) > 0:
            s = s + ", reverse:" + str(self.reverse)
        s = s + ")"
        return s

    def to_sql_implementation(self, db_model, *, using=None, temp_id_source=None):
        return db_model.extend_to_sql(self, using=using, temp_id_source=temp_id_source)


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
                  TableDescription('d', ['x', 'y']) .
                     extend({'z':_.x + _[var_name]/q + _get('x')})
                )
                print(ops)
    """

    ops: Dict[str, data_algebra.expr_rep.Expression]

    def __init__(self, ops, *, partition_by=None, order_by=None, reverse=None):
        data_algebra.pipe.PipeStep.__init__(self, name="Extend")
        self._ops = ops
        self.partition_by = partition_by
        self.order_by = order_by
        self.reverse = reverse

    def apply(self, other):
        return other.extend(
            ops=self._ops,
            partition_by=self.partition_by,
            order_by=self.order_by,
            reverse=self.reverse,
        )


class NaturalJoinNode(ViewRepresentation):
    by: List[str]
    jointype: str

    def __init__(self, a, b, *, by=None, jointype="INNER"):
        sources = [a, b]
        column_names = sources[0].column_names.copy()
        for ci in sources[1].column_names:
            if ci not in sources[0].column_set:
                column_names.append(ci)
        if isinstance(by, str):
            by = [by]
        by_set = set(by)
        if len(by) != len(by_set):
            raise Exception("duplicate column names in by")
        missing_left = by_set - a.column_set
        if len(missing_left) > 0:
            raise Exception("left table missing join keys: " + str(missing_left))
        missing_right = by_set - b.column_set
        if len(missing_right) > 0:
            raise Exception("right table missing join keys: " + str(missing_right))
        self.by = by
        self.jointype = jointype
        ViewRepresentation.__init__(self, column_names=column_names, sources=sources)

    def collect_representation_implementation(self, pipeline=None):
        if pipeline is None:
            pipeline = []
        od = collections.OrderedDict()
        od["op"] = "NaturalJoin"
        od["by"] = self.by
        od["jointype"] = self.jointype
        od["b"] = self.sources[1].collect_representation_implementation()
        pipeline.insert(0, od)
        return self.sources[0].collect_representation_implementation(pipeline=pipeline)

    def format_ops_implementation(self, indent=0):
        return (
            self.sources[0].format_ops_implementation(indent=indent)
            + " .\n"
            + " " * (indent + 3)
            + "natural_join(b=(\n"
            + " " * (indent + 6)
            + self.sources[1].format_ops_implementation(indent=indent + 6)
            + "),\n"
            + " " * (indent + 6)
            + "by="
            + str(self.by)
            + ", jointype="
            + self.jointype
            + ")"
        )

    def to_sql_implementation(self, db_model, *, using=None, temp_id_source=None):
        return db_model.natural_join_to_sql(
            self, using=using, temp_id_source=temp_id_source
        )


class NaturalJoin(data_algebra.pipe.PipeStep):
    _by: List[str]
    _jointype: str
    _b: ViewRepresentation

    def __init__(self, *, b=None, by=None, jointype="INNER"):
        if not isinstance(b, ViewRepresentation):
            raise Exception("b should be a ViewRepresentation")
        missing1 = set(by) - b.column_set
        if len(missing1) > 0:
            raise Exception("all by-columns must be in b-table")
        data_algebra.pipe.PipeStep.__init__(self, name="NaturalJoin")
        if isinstance(by, str):
            by = [by]
        by_set = set(by)
        if len(by) != len(by_set):
            raise Exception("duplicate column names in by")
        missing_right = by_set - b.column_set
        if len(missing_right) > 0:
            raise Exception("right table missing join keys: " + str(missing_right))
        self._by = by
        self._jointype = jointype
        self._b = b

    def apply(self, other):
        return other.natural_join(b=self._b, by=self._by, jointype=self._jointype)
