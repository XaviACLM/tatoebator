from tatoebator.external_download_requester import ExternalDownloadRequester, TatoebaDownloadable

from PyQt6.QtWidgets import QApplication, QWidget

from tatoebator.tatoebator import ExternalDownloadRequestConductor

app = QApplication([])

requester = ExternalDownloadRequester(ExternalDownloadRequestConductor)
requester.get_external_downloadable("ManyThingsTatoeba", prompt_user=True)