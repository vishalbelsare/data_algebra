import data_algebra.data_ops
import data_algebra.db_model


have_Spark = False
try:
    # noinspection PyUnresolvedReferences
    import pyspark
    import pyspark.sql

    have_Spark = True
except ImportError:
    have_Spark = False

# map from op-name to special SQL formatting code
SparkSQL_formatters = {"___": lambda dbmodel, expression: expression.to_python()}


class SparkConnection:
    def __init__(self, *, spark_context, spark_session):
        assert have_Spark
        assert isinstance(spark_context, pyspark.context.SparkContext)
        assert isinstance(spark_session, pyspark.sql.session.SparkSession)
        self.spark_context = spark_context
        self.spark_session = spark_session

    def close(self):
        if self.spark_conext is not None:
            self.spark_conext.stop()  # probably only for local demos
            self.spark_conext = None
        if self.spark_session is not None:
            self.spark_session = None


class SparkSQLModel(data_algebra.db_model.DBModel):
    """A model of how SQL should be generated for SparkSQL"""

    def __init__(self):
        data_algebra.db_model.DBModel.__init__(
            self,
            identifier_quote="`",
            string_quote='"',
            sql_formatters=SparkSQL_formatters,
        )

    def quote_identifier(self, identifier):
        if not isinstance(identifier, str):
            raise TypeError("expected identifier to be a str")
        if self.identifier_quote in identifier:
            raise ValueError('did not expect " in identifier')
        # TODO: see if we can get rid of the tolower conversion
        return self.identifier_quote + identifier.lower() + self.identifier_quote

    # noinspection PyMethodMayBeStatic
    def execute(self, conn, q):
        assert isinstance(conn, SparkConnection)
        assert isinstance(q, str)
        raise Exception("not implemented yet")

    def read_query(self, conn, q):
        assert isinstance(conn, SparkConnection)
        if isinstance(q, data_algebra.data_ops.ViewRepresentation):
            temp_tables = dict()
            q = q.to_sql(db_model=self, temp_tables=temp_tables)
            if len(temp_tables) > 1:
                raise ValueError("ops require management of temp tables, please collect them via to_sql(temp_tables)")
        else:
            q = str(q)
        res = conn.spark_session.sql(q)
        # or res.collect()
        return res.toPandas()  # TODO: make sure it is our dataframe type

    # noinspection PyMethodMayBeStatic
    def insert_table(
        self, conn, d, table_name, *, qualifiers=None, allow_overwrite=False
    ):
        assert isinstance(conn, SparkConnection)
        assert allow_overwrite
        d_spark = conn.spark_session.createDataFrame(d)
        d_spark.createOrReplaceTempView(table_name)  # TODO: non-temps and non allow_overwrite


def example_handle():
    """
    Return an example db handle for testing. Returns None if helper packages not present.

    """
    if not have_Spark:
        return None
    return SparkSQLModel().db_handle(
            SparkConnection(
                spark_context=pyspark.SparkContext(),
                spark_session=pyspark.sql.SparkSession.builder.appName('pandasToSparkDF').getOrCreate()))
