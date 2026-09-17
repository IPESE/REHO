{#-
  Page of one module in the API reference (sections/api.rst).

  Sphinx's default template only lists the members of a module in summary tables,
  which show the first line of each docstring and nothing else. This one renders
  the full documentation of every public class, function, exception and documented
  module attribute below its summary table.

  Only members defined in the module are listed (autosummary_imported_members is
  False), so the names that modules such as reho.model.reho re-export for backwards
  compatibility are documented once, where they are defined.
-#}
{{ fullname | escape | underline }}

.. automodule:: {{ fullname }}

{%- block modules %}
{#- The test-suite is not part of the API. Names are relative to the package. #}
{%- set submodules = modules | reject("equalto", "test") | list %}
{%- if submodules %}

Modules
-------

.. autosummary::
   :toctree:
   :recursive:
{% for item in submodules %}
   {{ item }}
{%- endfor %}
{%- endif %}
{%- endblock %}

{%- block classes %}
{%- if classes %}

Classes
-------
{%- if classes | length > 1 %}

.. autosummary::
   :nosignatures:
{% for item in classes %}
   {{ item }}
{%- endfor %}
{%- endif %}
{% for item in classes %}
.. autoclass:: {{ fullname }}.{{ item }}
   :members:
   :undoc-members:
   :show-inheritance:
{% endfor %}
{%- endif %}
{%- endblock %}

{%- block functions %}
{%- if functions %}

Functions
---------
{%- if functions | length > 1 %}

.. autosummary::
   :nosignatures:
{% for item in functions %}
   {{ item }}
{%- endfor %}
{%- endif %}
{% for item in functions %}
.. autofunction:: {{ fullname }}.{{ item }}
{% endfor %}
{%- endif %}
{%- endblock %}

{%- block exceptions %}
{%- if exceptions %}

Exceptions
----------
{% for item in exceptions %}
.. autoexception:: {{ fullname }}.{{ item }}
   :show-inheritance:
{% endfor %}
{%- endif %}
{%- endblock %}

{%- block attributes %}
{%- if attributes %}

Module attributes
-----------------
{% for item in attributes %}
.. autodata:: {{ fullname }}.{{ item }}
{% endfor %}
{%- endif %}
{%- endblock %}
