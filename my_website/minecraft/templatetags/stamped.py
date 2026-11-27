"""{% stamped 'css/x.css' %}: a static URL that carries the file's own mtime.

The pages used to append the current second to every stylesheet and script,
which did bust the cache - on every single request, so nothing was ever served
from it. A file's mtime changes exactly when the file does: an edit is picked
up at once and everything else is cached for as long as the browser likes.
"""

import os

from django import template
from django.templatetags.static import static

from minecraft.puller import static_root

register = template.Library()


@register.simple_tag
def stamped(path):
    try:
        stamp = int(os.path.getmtime(os.path.join(static_root(), path)))
    except OSError:
        stamp = 0
    return f'{static(path)}?v={stamp}'
