
from abc import ABC

import data_algebra.OrderedSet


# classes for holding object for SQL generation

# TODO: build a term object that carries the column use information


# encode and name a term for use in a SQL expression
def _enc_term(k, *, terms, db_model):
    v = None
    try:
        v = terms[k]
    except KeyError:
        pass
    if v is None:
        return db_model.quote_identifier(k)
    return v + " AS " + db_model.quote_identifier(k)


class NearSQL(ABC):
    """
    Represent SQL queries in a mostly string-form
    """

    def __init__(self, *, terms, quoted_query_name, temp_tables, is_table=False, annotation=None):
        assert isinstance(terms, (dict, type(None)))
        assert isinstance(quoted_query_name, str)
        assert isinstance(temp_tables, dict)
        assert isinstance(is_table, bool)
        assert isinstance(annotation, (str, type(None)))
        self.terms = None
        if terms is not None:
            self.terms = terms.copy()
        self.quoted_query_name = quoted_query_name
        self.is_table = is_table
        self.temp_tables = temp_tables.copy()
        self.annotation = annotation

    def to_near_sql(self, *, columns=None, force_sql=False, constants=None):
        return NearSQLContainer(
            near_sql=self,
            columns=columns,
            force_sql=force_sql,
            constants=constants)

    def to_sql(self, *, columns=None, force_sql=False, constants=None, db_model, annotate=False):
        raise NotImplementedError("base method called")

    # return a list where last element is a NearSQL previous elments are (name, NearSQLContainer) pairs
    def to_with_form(self):
        sequence = list()
        sequence.append(self)
        return sequence


class NearSQLContainer:
    """
    NearSQL with bound in columns, force_sql, and constants decisions
    """

    def __init__(self, *,
                 near_sql, columns=None, force_sql=False, constants=None):
        assert isinstance(near_sql, NearSQL)
        assert isinstance(columns, (set, data_algebra.OrderedSet.OrderedSet, list, type(None)))
        assert isinstance(force_sql, bool)
        assert isinstance(constants, (dict, type(None)))
        self.near_sql = near_sql
        self.columns = None
        if columns is not None:
            self.columns = columns.copy()
        self.columns = columns
        self.force_sql = force_sql
        self.constants = None
        if constants is not None:
            self.constants = constants.copy()

    def to_sql(self, db_model, annotate=False):
        return self.near_sql.to_sql(
            columns=self.columns,
            force_sql=self.force_sql,
            constants=self.constants,
            db_model=db_model,
            annotate=annotate)

    # assemble sub-sql
    def convert_subsql(self, *, db_model, annotate=False):
        assert isinstance(self, NearSQLContainer)
        assert isinstance(self.near_sql, NearSQL)
        if isinstance(self.near_sql, NearSQLTable):
            sql = (
                    " "
                    + self.to_sql(db_model, annotate=annotate)
                    + " "
            )
            if self.near_sql.quoted_query_name != self.near_sql.quoted_table_name:
                sql = sql + (
                        self.near_sql.quoted_query_name
                        + " "
                )
        elif isinstance(self.near_sql, NearSQLCommonTableExpression):
            sql = (
                    " "
                    + self.to_sql(db_model, annotate=annotate)
                    + " "
            )
        else:
            sql = (
                    " ( "
                    + self.to_sql(db_model, annotate=annotate)
                    + " ) "
                    + self.near_sql.quoted_query_name
                    + " "
            )
        return sql

    def to_with_form(self):
        if self.near_sql.is_table:
            sequence = list()
            sequence.append(self)
            return sequence
        sequence = self.near_sql.to_with_form()
        endi = len(sequence) - 1
        last_step = sequence[endi]
        sequence[endi] = NearSQLContainer(
            near_sql=last_step, columns=self.columns, force_sql=self.force_sql, constants=self.constants)
        return sequence


class NearSQLCommonTableExpression(NearSQL):
    def __init__(self, *, quoted_query_name):
        NearSQL.__init__(
            self, terms=None, quoted_query_name=quoted_query_name, temp_tables=dict(), is_table=True
        )

    def to_sql(self, *, columns=None, force_sql=False, constants=None, db_model, annotate=False):
        return self.quoted_query_name


class NearSQLTable(NearSQL):
    def __init__(self, *, terms, quoted_query_name, quoted_table_name):
        assert isinstance(terms, dict)
        NearSQL.__init__(
            self, terms=terms, quoted_query_name=quoted_query_name, temp_tables=dict(), is_table=True
        )
        self.quoted_table_name = quoted_table_name

    def to_sql(self, *, columns=None, force_sql=False, constants=None, db_model, annotate=False):
        if columns is None:
            columns = [k for k in self.terms.keys()]
        if len(columns) <= 0:
            force_sql = False
        have_constants = (constants is not None) and (len(constants) > 0)
        if force_sql or have_constants:
            terms_strs = [db_model.quote_identifier(k) for k in columns]
            if have_constants:
                terms_strs = terms_strs + [
                    v + " AS " + db_model.quote_identifier(k)
                    for (k, v) in constants.items()
                ]
            if len(terms_strs) < 1:
                terms_strs = [f'1 AS {db_model.quote_identifier("data_algebra_placeholder_col_name")}']
            return "SELECT " + ", ".join(terms_strs) + " FROM " + self.quoted_table_name
        return self.quoted_table_name


class NearSQLUnaryStep(NearSQL):
    def __init__(
        self,
        *,
        terms,
        quoted_query_name,
        sub_sql,
        suffix="",
        temp_tables,
        annotation=None
    ):
        assert isinstance(terms, dict)
        NearSQL.__init__(
            self,
            terms=terms,
            quoted_query_name=quoted_query_name,
            temp_tables=temp_tables,
            annotation=annotation
        )
        assert isinstance(sub_sql, NearSQLContainer)
        assert isinstance(suffix,  (str, type(None)))
        self.sub_sql = sub_sql
        self.suffix = suffix

    def to_sql(self, *, columns=None, force_sql=False, constants=None, db_model, annotate=False):
        if columns is None:
            columns = [k for k in self.terms.keys()]
        terms = self.terms
        if (constants is not None) and (len(constants) > 0):
            terms.update(constants)
        terms_strs = [_enc_term(k, terms=terms, db_model=db_model) for k in columns]
        if len(terms_strs) < 1:
            terms_strs = [f'1 AS {db_model.quote_identifier("data_algebra_placeholder_col_name")}']
        sql = "SELECT "
        if annotate and (self.annotation is not None) and (len(self.annotation) > 0):
            sql = sql + " -- " + self.annotation.replace('\r', ' ').replace('\n', ' ') + "\n "
        sql = sql + ", ".join(terms_strs) + " FROM " + self.sub_sql.convert_subsql(db_model=db_model, annotate=annotate)
        if (self.suffix is not None) and (len(self.suffix) > 0):
            sql = sql + " " + self.suffix
        return sql

    def to_with_form(self):
        if self.sub_sql.near_sql.is_table:
            # tables don't need to be re-encoded
            sequence = list()
            sequence.append(self)
            return sequence
        # non-trivial sequence
        sequence = self.sub_sql.to_with_form()
        endi = len(sequence) - 1
        last_step = sequence[endi]
        stub = last_step
        if not stub.near_sql.is_table:
            stub = NearSQLContainer(
                near_sql=NearSQLCommonTableExpression(quoted_query_name=last_step.near_sql.quoted_query_name)
            )
        sequence[endi] = (last_step.near_sql.quoted_query_name, last_step)
        stubbed_step = NearSQLUnaryStep(
            terms=self.terms,
            quoted_query_name=self.quoted_query_name,
            sub_sql=stub,
            suffix=self.suffix,
            temp_tables=self.temp_tables,
            annotation=self.annotation)
        sequence.append(stubbed_step)
        return sequence


class NearSQLBinaryStep(NearSQL):
    def __init__(
        self,
        *,
        terms,
        quoted_query_name,
        sub_sql1,
        joiner,
        sub_sql2,
        suffix="",
        temp_tables
    ):
        assert isinstance(terms, dict)
        NearSQL.__init__(
            self,
            terms=terms,
            quoted_query_name=quoted_query_name,
            temp_tables=temp_tables,
        )
        assert isinstance(sub_sql1,  NearSQLContainer)
        assert isinstance(sub_sql2, NearSQLContainer)
        assert isinstance(suffix,  (str, type(None)))
        assert isinstance(joiner, str)
        self.sub_sql1 = sub_sql1
        self.joiner = joiner
        self.sub_sql2 = sub_sql2
        self.suffix = suffix

    def to_sql(self, *, columns=None, force_sql=False, constants=None, db_model, annotate=False):
        if columns is None:
            columns = [k for k in self.terms.keys()]
        terms = self.terms
        if (constants is not None) and (len(constants) > 0):
            terms.update(constants)
        terms_strs = [_enc_term(k, terms=terms, db_model=db_model) for k in columns]
        if len(terms_strs) < 1:
            terms_strs = [f'1 AS {db_model.quote_identifier("data_algebra_placeholder_col_name")}']
        sql = (
                "SELECT " + ", ".join(terms_strs) + " FROM " + " ( "
                + self.sub_sql1.convert_subsql(db_model=db_model, annotate=annotate)
                + " " + self.joiner + " "
                + self.sub_sql2.convert_subsql(db_model=db_model, annotate=annotate)
                )
        if (self.suffix is not None) and (len(self.suffix) > 0):
            sql = sql + " " + self.suffix
        sql = sql + " ) "
        return sql


class NearSQLq(NearSQL):
    """
    Adapter to wrap a pre-existing query as a NearSQL

    """
    def __init__(
        self, *, quoted_query_name, query, terms, prev_quoted_query_name, temp_tables
    ):
        assert isinstance(terms, dict)
        NearSQL.__init__(
            self,
            terms=terms,
            quoted_query_name=quoted_query_name,
            temp_tables=temp_tables,
        )
        assert isinstance(query, str)
        assert isinstance(prev_quoted_query_name, str)
        self.query = query
        self.prev_quoted_query_name = prev_quoted_query_name

    def to_sql(self, *, columns=None, force_sql=False, constants=None, db_model, annotate=False):
        if columns is None:
            columns = [k for k in self.terms.keys()]
        terms = self.terms
        if (constants is not None) and (len(constants) > 0):
            terms.update(constants)

        def enc_term(k):
            v = terms[k]
            if v is None:
                return db_model.quote_identifier(k)
            return v + " AS " + db_model.quote_identifier(k)

        terms_strs = [enc_term(k) for k in columns]
        if len(terms_strs) < 1:
            terms_strs = [f'1 AS {db_model.quote_identifier("data_algebra_placeholder_col_name")}']
        return (
            "SELECT "
            + ", ".join(terms_strs)
            + " FROM ( "
            + self.query
            + " ) "
            + self.prev_quoted_query_name
        )
