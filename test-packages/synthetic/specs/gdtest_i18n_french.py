"""
gdtest_i18n_french — Tests i18n with French (Latin script).

Dimensions: K50
Focus: site.language: fr — all UI widgets render French translations.
All docstrings, user guide, and metadata are in French.
"""

SPEC = {
    "name": "gdtest_i18n_french",
    "description": (
        "i18n test with French (Latin script). Docstrings, user guide, and "
        "metadata are written in French for full native-language experience."
    ),
    "dimensions": ["K50"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-i18n-french",
            "version": "0.1.0",
            "description": "Outils de traitement de donn\u00e9es pour l'analyse scientifique",
            "license": "MIT",
            "authors": [
                {"name": "Marie Dupont", "email": "marie.dupont@exemple.fr"},
            ],
            "urls": {
                "Documentation": "https://gdtest-i18n-french.example.com",
                "Repository": "https://github.com/test-org/gdtest-i18n-french",
            },
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "site": {
            "language": "fr",
        },
        "announcement": "Bienvenue ! Consultez notre nouveau guide de d\u00e9marrage rapide.",
        "github_url": "https://github.com/test-org/gdtest-i18n-french",
        "dark_mode_toggle": True,
        "back_to_top": True,
        "copy_code": True,
        "page_metadata": True,
        "funding": {"name": "Fondation pour la Recherche"},
    },
    "files": {
        "gdtest_i18n_french/__init__.py": '''\
            """Outils de traitement de donn\u00e9es pour l'analyse scientifique."""

            __version__ = "0.1.0"
            __all__ = [
                "TraiteurDeDonnees",
                "transformer",
                "valider",
                "resumer",
            ]


            class TraiteurDeDonnees:
                """
                Traite et transforme des jeux de donn\u00e9es.

                Une classe polyvalente de traitement de donn\u00e9es qui prend
                en charge plusieurs formats d'entr\u00e9e et des pipelines de
                transformation configurables.

                Parameters
                ----------
                source : str
                    Chemin vers la source de donn\u00e9es.
                format : str
                    Format d'entr\u00e9e (csv, json, parquet).
                verbeux : bool
                    Afficher la progression dans le journal.

                See Also
                --------
                transformer
                    Applique une transformation d'\u00e9chelle aux donn\u00e9es.
                valider
                    Valide un enregistrement par rapport au sch\u00e9ma.

                Examples
                --------
                >>> proc = TraiteurDeDonnees("donnees.csv", format="csv")
                >>> proc.executer()
                {'statut': 'ok', 'lignes': 0}

                .. versionadded:: 0.1.0
                """

                def __init__(
                    self, source: str, format: str = "csv", verbeux: bool = False
                ):
                    self.source = source
                    self.format = format
                    self.verbeux = verbeux

                def executer(self) -> dict:
                    """
                    Ex\u00e9cute le pipeline de traitement.

                    Returns
                    -------
                    dict
                        R\u00e9sultats du traitement avec le statut et le nombre de lignes.
                    """
                    return {"statut": "ok", "lignes": 0}

                def reinitialiser(self) -> None:
                    """
                    R\u00e9initialise l'\u00e9tat du processeur.

                    Efface toutes les donn\u00e9es en cache et remet les compteurs
                    internes \u00e0 leurs valeurs initiales.
                    """
                    pass


            def transformer(donnees: list, echelle: float = 1.0) -> list:
                """
                Applique une transformation d'\u00e9chelle aux donn\u00e9es.

                Parameters
                ----------
                donnees : list
                    Valeurs de donn\u00e9es en entr\u00e9e.
                echelle : float
                    Multiplicateur \u00e0 appliquer.

                Returns
                -------
                list
                    Donn\u00e9es transform\u00e9es.

                .. versionchanged:: 0.1.0 Le param\u00e8tre echelle accepte maintenant les valeurs n\u00e9gatives.

                See Also
                --------
                TraiteurDeDonnees
                    Processeur de donn\u00e9es complet.
                resumer
                    Calcule des statistiques descriptives.
                """
                return [x * echelle for x in donnees]


            def valider(enregistrement: dict, strict: bool = True) -> bool:
                """
                Valide un enregistrement par rapport au sch\u00e9ma.

                Parameters
                ----------
                enregistrement : dict
                    L'enregistrement \u00e0 valider.
                strict : bool
                    Appliquer toutes les contraintes.

                Returns
                -------
                bool
                    True si l'enregistrement est valide.

                See Also
                --------
                transformer
                    Applique une transformation aux donn\u00e9es.
                .. deprecated:: 0.1.0
                    Utilisez la méthode TraiteurDeDonnees.valider() à la place.                """
                return True


            def resumer(valeurs: list[float]) -> dict:
                """
                Calcule des statistiques descriptives pour une liste de valeurs.

                Parameters
                ----------
                valeurs : list[float]
                    Valeurs num\u00e9riques \u00e0 r\u00e9sumer.

                Returns
                -------
                dict
                    Dictionnaire avec min, max, moyenne et nombre d'\u00e9l\u00e9ments.
                """
                if not valeurs:
                    return {"min": 0, "max": 0, "moyenne": 0, "nombre": 0}
                return {
                    "min": min(valeurs),
                    "max": max(valeurs),
                    "moyenne": sum(valeurs) / len(valeurs),
                    "nombre": len(valeurs),
                }
        ''',
        "user_guide/01-demarrage-rapide.qmd": """\
            ---
            title: "D\u00e9marrage rapide"
            guide-section: "Fondamentaux"
            ---

            # D\u00e9marrage rapide

            Ce guide vous accompagne dans les premi\u00e8res \u00e9tapes d'utilisation
            du paquet.

            ## Installation

            Installez avec pip :

            ```bash
            pip install gdtest-i18n-french
            ```

            ## Exemple rapide

            ```python
            from gdtest_i18n_french import TraiteurDeDonnees

            proc = TraiteurDeDonnees("donnees.csv")
            resultat = proc.executer()
            print(resultat)
            ```

            ## Formats pris en charge

            Le processeur accepte plusieurs formats de fichiers :

            | Format   | Extension | Flux continu |
            |----------|-----------|--------------|
            | CSV      | .csv      | Oui          |
            | JSON     | .json     | Non          |
            | Parquet  | .parquet  | Oui          |
        """,
        "user_guide/02-configuration.qmd": """\
            ---
            title: "Configuration"
            guide-section: "Fondamentaux"
            ---

            # Configuration

            Configurez le processeur avec diff\u00e9rentes options pour
            adapter son comportement \u00e0 vos besoins.

            ## Mode strict

            Le mode strict applique toutes les contraintes de validation :

            ```python
            from gdtest_i18n_french import valider

            resultat = valider({"nom": "test"}, strict=True)
            print(resultat)  # True
            ```

            ## Statistiques descriptives

            Obtenez un r\u00e9sum\u00e9 rapide de vos donn\u00e9es :

            ```python
            from gdtest_i18n_french import resumer

            stats = resumer([10.5, 20.3, 15.7, 8.2])
            print(stats)
            ```
        """,
        "user_guide/03-table-explorer.qmd": """\
            ---
            title: "Exploration de tableau"
            guide-section: "Fondamentaux"
            ---

            # Exploration de tableau

            Utilisez `tbl_explorer()` pour explorer vos donn\u00e9es de
            mani\u00e8re interactive.

            ```{python}
            #| echo: false
            import tempfile
            from great_docs import tbl_explorer
            rows = "nom,age,ville,score\\nMarie,28,Paris,92.5\\nPierre,35,Lyon,87.3\\nSophie,22,Marseille,95.1\\nJean,41,Toulouse,78.6\\nClaire,30,Nantes,88.9\\nLucas,27,Bordeaux,91.2\\nEmma,33,Lille,84.7"
            tf = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
            tf.write(rows)
            tf.close()
            tbl_explorer(tf.name)
            ```
        """,
        "README.md": """\
            # gdtest-i18n-french

            Outils de traitement de donn\u00e9es pour l'analyse scientifique.

            ## Fonctionnalit\u00e9s

            - Traitement de donn\u00e9es multi-format (CSV, JSON, Parquet)
            - Validation de sch\u00e9ma configurable
            - Statistiques descriptives int\u00e9gr\u00e9es

            ## Licence

            MIT
        """,
    },
    "expected": {
        "detected_name": "gdtest-i18n-french",
        "detected_module": "gdtest_i18n_french",
        "detected_parser": "numpy",
        "export_names": [
            "TraiteurDeDonnees",
            "resumer",
            "transformer",
            "valider",
        ],
        "num_exports": 4,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": True,
        "user_guide_files": [
            "01-demarrage-rapide.qmd",
            "02-configuration.qmd",
            "03-table-explorer.qmd",
        ],
    },
}
