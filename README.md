# Cover_Manager

Cover_Manager est une intégration personnalisée [Home Assistant](https://www.home-assistant.io/) qui pilote automatiquement plusieurs volets selon les horaires, la luminosité extérieure, la température et l'orientation solaire.

## Fonctionnalités

- Sélection de plusieurs entités `cover` dans une seule configuration.
- Horaires d'ouverture et de fermeture différents en semaine et le week-end.
- Passage automatique en mode jour ou nuit selon la luminosité extérieure.
- Délai configurable pour éviter les changements dus à une variation lumineuse passagère.
- Fermeture partielle lorsqu'il fait chaud et que le soleil atteint la façade.
- Hystérésis de température pour limiter les allers-retours autour du seuil de chaleur.
- Blocage de toute fermeture tant qu'une porte ou une fenêtre configurée est ouverte.
- Interrupteur pour mettre temporairement l'automatisme en pause.
- Capteur indiquant la règle active, la position cible et la raison de la décision.

## Installation

### Via HACS

1. Ajoutez ce dépôt comme intégration personnalisée dans HACS.
2. Installez **Cover_Manager**.
3. Redémarrez Home Assistant.

### Installation manuelle

1. Copiez `custom_components/cover_manager` dans le dossier `custom_components` de votre configuration Home Assistant.
2. Redémarrez Home Assistant.

> **Migration depuis l'ancien domaine `volets_manager` :** Home Assistant identifie une intégration par son domaine. Après ce renommage, supprimez l'ancienne intégration dans **Paramètres > Appareils et services**, retirez l'ancien dossier `custom_components/volets_manager`, installez la nouvelle version, puis ajoutez **Cover_Manager**. Les options de l'ancienne entrée devront être configurées à nouveau.

## Configuration

1. Dans **Paramètres > Appareils et services**, cliquez sur **Ajouter une intégration**.
2. Recherchez **Cover_Manager**.
3. Saisissez un nom pour le groupe et sélectionnez les volets à piloter.
4. Ouvrez ensuite **Configurer** pour ajuster les options.

### Options disponibles

| Option | Description |
| --- | --- |
| Volets à piloter | Entités `cover` contrôlées par l'intégration |
| Heure d'ouverture | Début de la plage de jour en semaine |
| Heure de fermeture | Fin de la plage de jour en semaine |
| Ouverture / fermeture (week-end) | Horaires facultatifs différents pour samedi et dimanche |
| Capteur de luminosité extérieure | Mesure utilisée pour détecter le jour et la nuit |
| Seuil d'ouverture | Luminosité minimale pour passer en mode jour |
| Seuil de fermeture | Luminosité sous laquelle passer en mode nuit |
| Délai de confirmation | Durée pendant laquelle la condition doit rester vraie |
| Capteur de température extérieure | Mesure utilisée pour activer le mode chaleur |
| Seuil de chaleur | Température d'entrée dans le mode chaleur |
| Position en cas de chaleur | Pourcentage d'ouverture demandé, par exemple `30 %` |
| Azimut solaire min / max | Plage d'azimut correspondant à la façade |
| Élévation solaire minimale | Hauteur minimale du soleil pour prendre en compte la chaleur |
| Capteurs d'ouverture | Fenêtres ou portes qui bloquent toute fermeture |

## Règles de fonctionnement

L'intégration évalue les règles toutes les minutes et lors de tout changement des capteurs configurés.

- **Nuit** : entre la fermeture et l'ouverture, les volets sont fermés à `0 %`.
- **Jour** : dans la plage horaire et lorsque les conditions lumineuses sont remplies, les volets sont ouverts à `100 %`.
- **Chaleur** : si la température dépasse le seuil, que le soleil éclaire la façade et que l'élévation est suffisante, les volets prennent la position de chaleur configurée.
- **Pause** : aucun ordre n'est envoyé tant que l'interrupteur est désactivé.

La position cible n'est envoyée que lorsqu'elle change par rapport à la dernière cible enregistrée pour chaque volet. Cela évite de rouvrir systématiquement un volet déplacé manuellement tant qu'une nouvelle règle ne doit pas être appliquée.

## Entités créées

Pour chaque configuration, Cover_Manager crée :

- un interrupteur nommé **Automatisme actif** ;
- un capteur nommé **Règle active**.

Le capteur expose les attributs suivants :

- `position_cible` : position demandée, de `0` à `100`, ou `null` en pause ;
- `raison` : explication lisible de la règle courante ;
- `fermeture_bloquee_par` : liste des ouvertures ayant empêché une fermeture.

## Exemple d'utilisation

Avec les valeurs suivantes :

- horaires : `08:00` à `20:00` ;
- seuil d'ouverture : `500 lx` ;
- seuil de fermeture : `200 lx` ;
- seuil de chaleur : `26 °C` ;
- position de chaleur : `30 %`.

Les volets restent fermés la nuit ou sous `200 lx`, passent à l'ouverture lors d'une période lumineuse soutenue au-dessus de `500 lx`, puis se mettent à `30 %` si une façade est exposée au soleil et que la température dépasse `26 °C`.

## Dépannage

- Vérifiez que les entités de capteur utilisent des états numériques.
- Vérifiez que les entités `cover` prennent en charge l'ouverture/fermeture ou la position.
- Si une fermeture est bloquée, contrôlez les entités sélectionnées dans **Capteurs d'ouverture**.
- Activez les journaux Home Assistant pour voir les décisions et blocages détaillés :

```yaml
logger:
  default: info
  logs:
    custom_components.cover_manager: debug
```

## Compatibilité

Cette intégration utilise uniquement les services et entités standards de Home Assistant. Elle dépend optionnellement de l'entité `sun.sun` pour le calcul de l'exposition solaire.
