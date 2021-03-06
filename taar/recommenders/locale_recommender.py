# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from srgutil.interfaces import IMozLogging
from .base_recommender import AbstractRecommender
from .lazys3 import LazyJSONLoader

from .s3config import TAAR_LOCALE_BUCKET
from .s3config import TAAR_LOCALE_KEY


class LocaleRecommender(AbstractRecommender):
    """ A recommender class that returns top N addons based on the client geo-locale.

    This will load a json file containing updated top n addons in use per geo locale
    updated periodically by a separate process on airflow using Longitdudinal Telemetry
    data.

    This recommender may provide useful recommendations when collaborative_recommender
    may not work.
    """
    def __init__(self, ctx):
        self._ctx = ctx

        self.logger = self._ctx[IMozLogging].get_logger('taar')

        self._top_addons_per_locale = LazyJSONLoader(self._ctx,
                                                     TAAR_LOCALE_BUCKET,
                                                     TAAR_LOCALE_KEY)

        self._init_from_ctx()

    @property
    def top_addons_per_locale(self):
        return self._top_addons_per_locale.get()[0]

    def _init_from_ctx(self):
        if self.top_addons_per_locale is None:
            self.logger.error("Cannot download the top per locale file {}".format(TAAR_LOCALE_KEY))

    def can_recommend(self, client_data, extra_data={}):
        # We can't recommend if we don't have our data files.
        if self.top_addons_per_locale is None:
            return False

        # If we have data coming from other sources, we can use that for
        # recommending.
        client_locale = client_data.get('locale', None) or extra_data.get('locale', None)
        if not isinstance(client_locale, str):
            return False

        if client_locale not in self.top_addons_per_locale:
            return False

        if not self.top_addons_per_locale.get(client_locale):
            return False

        return True

    def recommend(self, client_data, limit, extra_data={}):
        # If we have data coming from multiple sourecs, prefer the one
        # from 'client_data'.
        client_locale = client_data.get('locale') or extra_data.get('locale', None)
        result_list = self.top_addons_per_locale.get(client_locale, [])[:limit]

        if 'locale' not in client_data:
            try:
                client_data['locale'] = extra_data["locale"]
            except KeyError:
                client_data['locale'] = None

        log_data = (client_data['locale'],
                    str([r for r in result_list]))
        self.logger.info("locale_recommender_triggered, "
                         "client_locale: [%s], guids: [%s]" % log_data)
        # Need to have the actual prevalence here in order to improve this.
        return [(x, 1.0) for x in result_list]
