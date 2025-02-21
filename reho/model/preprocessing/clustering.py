from pyclustering.cluster.kmedoids import kmedoids
from pyclustering.utils.metric import distance_metric, type_metric
from pyclustering.utils import calculate_distance_matrix
import numpy as np
import pandas as pd

__doc__ = """
Clustering algorithm for input data reduction.
"""


class Clustering:
    """
    Executes a clustering for each number of clusters among a specified interval (nb_clusters),
    and selects the optimal one according to the MAPE criterion (Mean Average Percentage Error).

    Parameters:
    -----------
    data : pd.DataFrame
        Annual weather data
    nb_clusters : list
        Interval for the number of clusters possible.
    """

    def __init__(self, data, nb_clusters=None, period_duration=24, options=None):
        """
        Initializes the Clustering object with the given parameters.
        """
        self.nb_clusters = nb_clusters if nb_clusters is not None else [8]
        self.data_org = data
        self.period_duration = period_duration
        self.data_nor = None
        self.attr_org, self.attr_nor = [], []
        self.mod_org, self.mod_nor = [], []
        self.option = options or {"year-to-day": True, "extreme": [(1, "min"), (2, "max")]}
        self.results = {"idx": None}
        self.attr_clu = None
        self.kpis_clu, self.nbr_opt = None, None

    def run_clustering(self):
        self.__do_normalization()
        self.__execute_clustering()
        self.__compute_kpis()
        self.__select_optimal()

    def __do_normalization(self):
        """
        Normalizes the data and reshapes it for clustering based on the defined period (e.g., daily).
        """
        self.data_nor = self.data_org.apply(lambda col: (col - col.min()) / (col.max() - col.min()))

        for col in self.data_org.columns:
            if self.option["year-to-day"]:
                nbr_p = int(self.data_nor.shape[0] // self.period_duration)  # ! integer division / number of periods default: 365
                self.modulo = int(self.data_nor.shape[0] % self.period_duration)
                stop = self.data_nor.shape[0] - self.modulo
                self.attr_org.append(np.reshape(self.data_org.loc[: (stop - 1), col].tolist(), (nbr_p, self.period_duration)))
                self.attr_nor.append(np.reshape(self.data_nor.loc[: (stop - 1), col].tolist(), (nbr_p, self.period_duration)))
                self.mod_org.append(self.data_org.loc[stop:, col].tolist())
                self.mod_nor.append(self.data_nor.loc[stop:, col].tolist())
            else:
                self.attr_org.append(self.data_org[col].values.reshape(-1, 1))
                self.attr_nor.append(self.data_nor[col].values.reshape(-1, 1))

        self.attr_org = np.hstack(self.attr_org)
        self.attr_nor = np.hstack(self.attr_nor)

    @staticmethod
    def __run_KMedoids(matrix, n_clusters):
        """
        Runs the K-Medoids algorithm on the given matrix for a specified number of clusters.
        """
        if len(matrix) == 1:
            return pd.DataFrame([1], columns=[str(n_clusters)])

        metric = distance_metric(type_metric.EUCLIDEAN_SQUARE)
        dist_matrix = calculate_distance_matrix(matrix, metric)
        initial_medoids = np.random.choice(len(matrix), n_clusters, replace=False).tolist()

        kmedoids_instance = kmedoids(dist_matrix, initial_medoids, ccore=False, data_type='distance_matrix')  # ccore=False, otherwise incompatible with ARM64
        kmedoids_instance.process()

        cluster_assignments = np.zeros(len(matrix), dtype=int)
        for cluster_idx, cluster_points in enumerate(kmedoids_instance.get_clusters()):
            for point in cluster_points:
                cluster_assignments[point] = kmedoids_instance.get_medoids()[cluster_idx]

        return pd.DataFrame({str(n_clusters): cluster_assignments})

    def __execute_clustering(self):
        """
        Executes the K-Medoids clustering for each number of clusters, keeping clustering per month,
        but concatenates results to form a yearly DataFrame with the correct shape (365, 1).
        """
        df_res = pd.DataFrame()

        # Define day ranges for each month (0-based indexing)
        month_day_ranges = {
            1: (0, 31), 2: (31, 59), 3: (59, 90), 4: (90, 120),
            5: (120, 151), 6: (151, 181), 7: (181, 212), 8: (212, 243),
            9: (243, 273), 10: (273, 304), 11: (304, 334), 12: (334, 365)
        }

        # Loop over each number of clusters
        for n_clusters in self.nb_clusters:

            # Create a temporary DataFrame to store the results for the year
            year_results = pd.DataFrame()

            # Loop through each month
            for month, (start, end) in month_day_ranges.items():
                # Slice self.attr_nor for the current month
                month_attr_nor = self.attr_nor[start:end, :]

                # Apply K-Medoids clustering for the current month
                df = self.__run_KMedoids(month_attr_nor, n_clusters)
                df[str(n_clusters)] = df[str(n_clusters)] + start
                # Ensure the correct date index for the month
                df.index = self.data_org.index[start:end]

                # Concatenate the results for each month into the yearly DataFrame
                year_results = pd.concat([year_results, df], axis=0)

            df_res[str(n_clusters)] = year_results[str(n_clusters)]

        df_res.columns.name = "iteration"
        self.results["idx"] = df_res
    #
    # def __execute_clustering(self):
    #     """
    #     Executes the K-Medoids clustering for each number of clusters.
    #     """
    #     df_res = pd.DataFrame()
    #     for n_clusters in self.nb_clusters:
    #         print('Applying algorithm for', n_clusters, 'clusters')
    #         df = self.__run_KMedoids(self.attr_nor, n_clusters)
    #         df_res[str(n_clusters)] = df[str(n_clusters)]
    #
    #     df_res.columns.name = "iteration"
    #     self.results["idx"] = df_res


    def __compute_kpis(self):
        """
        Computes key performance indicators (KPIs) for the clustering results.
        """
        kpi_frames = []
        frm_clus = []
        for sol in self.results["idx"].columns:
            self.attr_clu, data_clu = self.__do_attr_clu(sol)
            kpi_frame = self.__compute_metrics(data_clu)
            kpi_frames.append(kpi_frame)
            frm_clus.append(data_clu)

        self.kpis_clu = pd.concat(kpi_frames, keys=self.results["idx"].columns, names=["iteration"])
        self.attr_clu = pd.concat(frm_clus, keys=self.results["idx"].columns, names=["iteration"])

    def __compute_metrics(self, data_clu):
        """
        Computes the LDC, MAE, RMSD, and MAPE for the clustering solution.
        """
        pi = pd.DataFrame(index=["LDC", "MAE", "RMSD", "MAPE"], columns=self.data_org.columns)
        pi.loc["LDC"] = (abs(np.sort(data_clu.values, axis=0) - np.sort(self.data_nor.values, axis=0)).sum() /
                         self.data_nor.values.sum())
        pi.loc["MAE"] = (abs(self.data_nor - data_clu).sum()) / len(data_clu)
        pi.loc["RMSD"] = np.sqrt(((self.data_nor - data_clu) ** 2).mean())
        pi.loc["MAPE"] = (abs(self.data_nor - data_clu).sum() / self.data_nor.mean()) / len(data_clu)
        return pi

    def __do_attr_clu(self, sol):
        """
        Constructs the clustered attributes and returns them as a dataframe.
        """

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
                df[id_col] = np.reshape(attr_clu[:, int(self.period_duration * num):int(self.period_duration * (num + 1))], (self.data_org.shape[0] - self.modulo, 1)).flatten()
        else:
            df = pd.DataFrame(data=attr_clu, index=self.data_org.index, columns=self.data_org.columns)

        # create df from the modulo data and append to cluster
        df_mod = pd.DataFrame.from_dict(dict(zip(self.data_org.columns, self.mod_nor)))
        df = pd.concat([df, df_mod], ignore_index=True)

        return attr_clu, df

    def __select_optimal(self):
        """
        Selects the optimal number of clusters based on the MAPE criterion.
        """
        # - Define local variables
        kpis = self.kpis_clu
        iterations = kpis.index.get_level_values(0).unique()  # Get unique iteration values
        diff = pd.DataFrame(index=kpis.index, columns=kpis.columns)
        self.nbr_opt = max(iterations)

        # - Iterate over solutions
        for idx, iteration in enumerate(iterations):
            if idx < len(iterations) - 1:
                # Calculate the difference between consecutive iterations
                next_iteration = iterations[idx + 1]
                diff.loc[iteration] = kpis.loc[next_iteration] - kpis.loc[iteration]

                # Condition: check if MAPE doesn't improve by more than 1% for both dimensions
                mape_diff_text = diff.loc[(iteration, "MAPE"), "Text"]
                mape_diff_irr = diff.loc[(iteration, "MAPE"), "Irr"]
                condition = (mape_diff_text > -0.01) and (mape_diff_irr > -0.01)

                # If condition met, set the optimal number of clusters
                if condition:
                    self.nbr_opt = iteration
                    break

        print("N_k optimal: " + str(self.nbr_opt))
