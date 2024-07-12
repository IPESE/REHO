import pandas as pd
import numpy as np
import scipy.spatial
from sklearn_extra.cluster import KMedoids
from sklearn.metrics import pairwise_distances

__doc__ = """
Clustering algorithm for input data reduction.
"""


class Clustering:
    """
    Executes a clustering for each number of clusters among a specified interval (nb_clusters), and selects the optimal one according to the MAPE criterion (Mean Average Percentage Error).

    Parameters
    ----------
    data : pd.DataFrame
        Annual weather data
    nb_clusters : list
        Interval for the number of clusters possible.

    """

    def __init__(self, data, nb_clusters=None, option=None, pd=None, outliers=None):
        super().__init__()
        if nb_clusters is None:
            self.nb_clusters = [8]
        else:
            self.nb_clusters = nb_clusters

        # org - original, nor - normalized, clu - clustered

        self.outlier_removal = outliers

        self.data_org = data  # input data- df: attribute vectors as columns
        self.data_nor = None
        self.attr_org = []  # matrix or attributes, arrays:  len(attr_org) = total number of periods per year, len(attr_org[0])= number of attributes x period duration
        self.attr_nor = []
        self.attr_clu = None
        self.mod_org = []  # modulo data, f.e. last day of year (24hrs) for  pd = 7*24
        self.mod_nor = []
        if option is None:
            self.option = {"year-to-day": True, "extreme": [(1, "min"), (2, "max")]}
        else:
            self.option = option

        self.results = {"idx": None}  # pd.DataFrame()

        self.kpis_clu = None
        self.nbr_opt = None

        if pd is None:  # period duration, f.e. 1 period = 1 day => pd =  24 (default)
            self.pd = 24
        else:
            self.pd = pd

    def run_clustering(self):
        self.__do_normalization()
        self.__execute_clustering()
        self.__compute_kpis()
        self.__select_optimal()

    def __do_normalization(self):
        # - Load data set
        self.data_nor = pd.DataFrame([], index=self.data_org.index, columns=self.data_org.columns)
        # - Create dissimilarity matrix
        for id, col in enumerate(self.data_org):
            self.data_nor.loc[:, col] = ((self.data_org.loc[:, col] - self.data_org.loc[:, col].min()) / (
                        self.data_org.loc[:, col].max() - self.data_org.loc[:, col].min()))  # normalize
            # - OPTION : re-arrange dataframe
            if self.option["year-to-day"]:
                nbr_p = int(self.data_nor.shape[0] // self.pd)  # ! integer division / number of periods default: 365
                self.modulo = int(self.data_nor.shape[0] % self.pd)
                stop = self.data_nor.shape[0] - self.modulo
                self.attr_org.append(np.reshape(self.data_org.loc[: (stop - 1), col].tolist(), (nbr_p, self.pd)))
                self.attr_nor.append(np.reshape(self.data_nor.loc[: (stop - 1), col].tolist(), (nbr_p, self.pd)))
                self.mod_org.append(self.data_org.loc[stop:, col].tolist())
                self.mod_nor.append(self.data_nor.loc[stop:, col].tolist())
            else:
                self.attr_org.append(np.reshape(self.data_org.loc[:, col].tolist(), (self.data_org.shape[0], 1)))
                self.attr_nor.append(np.reshape(self.data_nor.loc[:, col].tolist(), (self.data_org.shape[0], 1)))

        self.attr_org = np.hstack(self.attr_org)
        self.attr_nor = np.hstack(self.attr_nor)

    @staticmethod
    def __run_KMedoids(matrix, n_clusters):

        if len(matrix) == 1:  # check for trivial solution
            df_res = pd.DataFrame([1], columns=['1'])

        else:

            print('Applying algorithm for', n_clusters, 'clusters')

            dist_a = pairwise_distances(matrix, metric='sqeuclidean')
            kmedoids = KMedoids(n_clusters=n_clusters, method='pam', random_state=42)
            kmedoids.fit(dist_a)

            cluster_assignments = kmedoids.labels_
            medoid_indices = kmedoids.medoid_indices_

            label_to_medoid = dict(zip(np.unique(cluster_assignments), medoid_indices))
            mapped_cluster_assignments = np.vectorize(label_to_medoid.get)(cluster_assignments)

            df_res = pd.DataFrame()
            df_res[str(n_clusters)] = mapped_cluster_assignments

        return df_res

    def __execute_clustering(self):

        df_res = pd.DataFrame()  # initialize df for results

        for i, c in enumerate(self.nb_clusters):
            df = self.__run_KMedoids(self.attr_nor, c)
            df_res[str(c)] = df[str(c)]

        if self.outlier_removal:
            for i, c in enumerate(self.nb_clusters):
                ncluster = c

                medoids = df_res[str(ncluster)].unique()  # Warning periods start with 1, python with 0

                df_distance = pd.DataFrame()

                for med in medoids:
                    group = df_res[df_res[str(ncluster)] == med]
                    df_attr = pd.DataFrame(self.attr_nor)

                    group_matrix = df_attr.loc[group.index]  # all periods allocated to medoid
                    group_vector = group_matrix.loc[med - 1]  # get medoid as vector

                    np_group_matrix = group_matrix.to_numpy()
                    np_group_vector = group_vector.to_numpy().reshape(1, -1)

                    dist = scipy.spatial.distance.cdist(np_group_vector, np_group_matrix)  # calculate distance to medoid

                    df_med = pd.DataFrame(dist[0], index=group_matrix.index)

                    df_distance = df_distance.append(df_med)

                if 'nlargest' in self.outlier_removal.keys():
                    outliers = df_distance.nlargest(self.outlier_removal['nlargest'], 0)
                elif 'distance' in self.outlier_removal.keys():
                    outliers = df_distance[df_distance[0] > self.outlier_removal['distance']]

                else:
                    raise "outlier removal not specified use for example {'nlargest': 3} or {'distance':1}"

                without_outliers = np.delete(self.attr_nor, outliers.index, axis=0)
                df = self.__run_KMedoids(without_outliers, ncluster)

                s = df.apply(lambda x: self.__return_typical_periods_outliers(x, x[str(ncluster)], outliers.index), axis=1)
                s = s.set_index(0)
                for o in outliers.index:
                    s.at[o, 1] = o
                df_res[str(c)] = s[1].sort_index()

        df_res.columns.name = "iteration"
        for col in df_res.columns:
            # - Rename extreme day index
            df_res.loc[df_res.loc[:, col] == 0, col] = df_res.loc[df_res.loc[:, col] == 0, col].index
        self.results["idx"] = df_res

    @staticmethod
    def __return_typical_periods_outliers(idx, clusters, outliers):
        index = idx.name
        outliers = outliers.sort_values()
        outlier_position = []  # find outlier position in new index
        for c, id in enumerate(outliers):
            outlier_position.append(id - c)
        outlier_position = np.array(outlier_position)

        outliers_before_period = outlier_position[outlier_position <= clusters]
        outliers_before_index = outlier_position[outlier_position <= index]

        if len(outliers_before_period) == 0:
            cluster = clusters
            if len(outliers_before_index) == 0:
                period = index
            else:
                period = index + len(outliers_before_index)
        else:
            cluster = clusters + len(outliers_before_period)
            if len(outliers_before_index) == 0:
                period = index
            else:
                period = index + len(outliers_before_index)

        return pd.Series([period, cluster])

    def __compute_kpis(self):
        frm_kpis = []
        frm_clus = []
        # - Iterate through solutions
        for sol in self.results["idx"]:
            # - Assess extreme periods
            self.__compute_extreme(sol)
            # - Assess clustered year
            attr_clu, data_clu = self.__do_attr_clu(sol)
            # data_clu annual dataframe, build with clustered periods to reach 8760 rows
            # attr_clu matrix, same size as attr_org but with clustered attributes
            # - Assess KPIs
            pi = pd.DataFrame(index=pd.Index(["LDC", "MAE", "RMSD", "MAPE"], name="kpi"), columns=pd.Index(self.data_org.columns, name="dimension"))
            # - LDC error
            pi.loc["LDC", :] = sum(abs(np.sort(data_clu.values, axis=0) - np.sort(self.data_nor.values, axis=0))) / sum(self.data_nor.values)
            # - MAE
            pi.loc["MAE", :] = (1 / data_clu.shape[0]) * abs(self.data_nor - data_clu).sum()
            # - RMSD
            pi.loc["RMSD", :] = ((1 / data_clu.shape[0]) * ((self.data_nor - data_clu) ** 2).sum()).apply(np.sqrt)
            # - MASE
            # diff = abs(self.data_N.shift() - self.data_N).sum() * (df_N.shape[0]) / (df_N.shape[0] -1)
            pi.loc["MAPE", :] = (1 / data_clu.shape[0]) * abs(self.data_nor - data_clu).sum() / (self.data_nor.mean())
            # - Append
            frm_kpis.append(pi)
            frm_clus.append(data_clu)
        # - Assign
        self.kpis_clu = pd.concat(frm_kpis, keys=self.results["idx"].columns, names=["iteration"], axis=1)
        self.attr_clu = pd.concat(frm_clus, keys=self.results["idx"].columns, names=["iteration"], axis=1)

    def __do_attr_clu(self, sol):
        # - Create clustered data
        idx = [x - 1 for x in self.results["idx"].loc[:, sol].tolist()]  # - Warning python index starts with 0!
        attr_clu = []
        for id in idx:
            id = int(id)
            attr_clu.append(self.attr_nor[id, :])

        # attr_clu.append(np.hstack(self.mod_nor))
        attr_clu = np.array(attr_clu)

        # - OPTION : re-arrange dataframe
        if self.option["year-to-day"]:
            df = pd.DataFrame(columns=self.data_org.columns)
            # nbr_t = int(self.data_nor.shape[0] / 365)
            for num, id_col in enumerate(df):
                df[id_col] = np.reshape(attr_clu[:, int(self.pd * num):int(self.pd * (num + 1))], (self.data_org.shape[0] - self.modulo, 1)).flatten()
        else:
            df = pd.DataFrame(data=attr_clu, index=self.data_org.index, columns=self.data_org.columns)

        # create df from the modulo data and append to cluster
        df_mod = pd.DataFrame.from_dict(dict(zip(self.data_org.columns, self.mod_nor)))
        df = df.append(df_mod, ignore_index=True)

        return attr_clu, df

    def __select_optimal(self):
        # - Define local variables
        kpis = self.kpis_clu.stack(["dimension"])
        diff = pd.DataFrame(index=kpis.index, columns=kpis.columns)
        self.nbr_opt = max(self.nb_clusters)
        # - Iterate over solutions
        for id, n_k in enumerate(kpis):
            if id < kpis.shape[1] - 1:
                diff.iloc[:, id] = (kpis.iloc[:, id + 1] - kpis.iloc[:, id])
                condition = (diff.loc[("MAPE", slice(None)), n_k] > -0.01).all()  # optimum condition: MAPE doesn't improve more than 1%
                if condition:
                    self.nbr_opt = n_k
                    break
        # print(diff)
        print("N_k optimal: " + str(self.nbr_opt))

    def __compute_extreme(self, sol):

        def find_nearests(array, value):
            array = np.asarray(array)
            dif = array - value
            if array.ndim > 1:
                dif[dif < 0] = 1e3
                idx = np.where(dif == np.amin(dif))
                id = idx[0][0]
                val = array[id, :]
            else:
                idx = (np.abs(array - value)).argmin()
                id = idx
                val = array[idx]
            return val, id

        # - Iterate over extreme options
        for id_dim in self.option["extreme"]:
            # - OPTION : re-arrange dataframe
            if self.option["year-to-day"]:
                nbr_t = self.pd  # int(self.data_nor.shape[0] / 365)
                id_str = int((id_dim[0] - 1) * nbr_t)
                id_end = int(id_dim[0] * nbr_t)
            else:
                id_str = int(id_dim[0])
                id_end = int(id_dim[0])
            # - Alter index
            if id_dim[1] == "max":
                _, max_id = find_nearests(self.attr_org[:, id_str:id_end], np.percentile(self.attr_org[:, id_str:id_end], 99))
                self.results["idx"].loc[max_id, sol] = max_id + 1  # - Warning -> index starts from 1!
            else:
                _, min_id = find_nearests(self.attr_org[:, id_str:id_end], np.percentile(self.attr_org[:, id_str:id_end], 1))
                self.results["idx"].loc[min_id, sol] = min_id + 1  # - Warning -> index starts from 1!
