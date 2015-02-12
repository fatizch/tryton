Ensemble de contrats - Informations sur quittances aggrégées
============================================================

TODO: deplacer texte dans summary.rst|features.rst|user/*.rst

Le module contract_set_invoice_report permet de mettre à disposition
d'un modèle de lettre les informations sur les quittances aggrégées d'un
ensemble de contrat.  A l'intérieur d'un ensemble de contrat (contract.set),
les contrats sont groupés par mode de paiement, par numéro du compte de
prélèvement, et par date de prochain renouvellement. A l'intérieur de
chaque groupe, les quittances pour une même date de prélèvement, pour
le cas d'un paiement par prélèvement, ou pour un même date de début
d'échéance, pour le cas d'un paiement par chèque, sont sommées entre elles.

Dans un modèle de lettre, il est alors possible d'afficher les montants des
quittances aggrégées par groupes de contrats en itérant sur la fonction
contract_groups_info avec un modèle de lettre de ce type :

<for each="contract_set in objects">
<for each="group in contract_set.contract_groups_info()">
<for each="invoice in group['invoices']">
<invoice.planned_payment_date>
<invoice.total_amount>
</for>
</for>
</for>

Additionally, one can access a list of dictionnaries containing
the details of each of the base invoices aggregated in the invoice object like
so :

<for each="contract_set in objects">
<for each="group in contract_set.contract_groups_info()">
<for each="invoice in group['invoices']">
<for each="base_invoice in invoice['base_invoices']">
<base_invoice['start']>
<base_invoice['end']>
<base_invoice['total_amount']>
</for>
</for>
</for>
</for>

Résumé
------

.. include:: summary.rst

Fonctionnalités
---------------

.. include:: features.rst


.. toctree::
    :hidden:

    summary.rst
    features.rst
