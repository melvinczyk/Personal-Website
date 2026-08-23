from django.shortcuts import render

from minecraft.views import LIVE_MAP, LIVE_MAP_VIEW


def index(request):
	# The codec's portal panel shows a corner of the same live map the portal
	# itself opens, so the address is read from the one place it is written
	# down rather than copied into a script.
	return render(request, 'index.html', {
		'map_url': LIVE_MAP + LIVE_MAP_VIEW,
	})
