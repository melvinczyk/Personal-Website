import os

from django.shortcuts import render

from minecraft.puller import static_root
from minecraft.views import summary


def _voices():
    """The codec lines that have a recording, so the page never asks for one that does not."""
    try:
        names = os.listdir(os.path.join(static_root(), 'audio', 'codec'))
    except OSError:
        return []
    return sorted(n[:-4] for n in names if n.endswith('.m4a'))


def index(request):
    # The codec's portal panel is a window onto the portal, so its numbers,
    # thumbnails and map address come from the same place the portal's do.
    return render(request, 'index.html', {'mc': summary(), 'voices': _voices()})
