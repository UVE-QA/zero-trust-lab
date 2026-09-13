# Design — a mobile unit the lab can ask, and cannot command

**Status:** decided and half built. The owner said yes, with an allowlist of
exactly one command: the light clean of the cat area. The lab side exists and
is tested; the hub side is drafted and waits for the household session to
correct it and the owner to approve it there. Nothing on the hub has changed.

The lab has a role, `tag:drone`, for a unit that both reports and takes
commands. It has never had a device. The candidate is the house's robot vacuum:
a real machine that moves, in a real home, with a real risk of annoying the
people and the cat who live there. That last part is the design problem.

---

## What the vacuum is, factually

Checked on the hub by the session that manages the house, not assumed:

- **It cannot run a tailnet client.** It is a vendor appliance.
- **Its control path already leaves the house.** The hub reaches it through the
  vendor's cloud, not over the home network: hub → vendor cloud → robot,
  measured at about 20 seconds from command to movement.
- **The hub can command a lot**: start, pause, stop, return to dock, spot and
  area cleaning, five named vendor scenarios, fan speed, water level, cleaning
  mode, do-not-disturb, child lock, auto-empty, map deletion, and a raw
  passthrough command.
- **It reports plenty**: state, battery, task and dock status, errors, current
  and lifetime cleaning area and time, and consumable hours.

## What that means for the lab

**It does not make `tag:drone` a live node.** Nothing here joins the tailnet;
the role stays unhomed and the diagram keeps saying so. What this design buys
is the tier the lab has never demonstrated: *a request for physical action,
crossing from a machine outside the house to a machine inside it, without the
outside gaining any way in.*

## The invariant

The collector lives outside the house. It has no path into the house, by
policy and by test (D-049). **This design must not create one.** That rules
out the two obvious shapes:

| shape | why not |
|---|---|
| a webhook on the hub | needs `collector → hub:8123`, the widening the telemetry design was built to avoid; and a webhook id is a bearer secret |
| an MQTT topic on the house broker | needs `collector → hub:1883`, and that broker's access list is not enforced — every login is effectively a superuser (D-048) |

## The shape that keeps it

**The hub asks; the collector answers; the house decides.**

On the tick it already runs, the hub makes one outbound call to the collector
and reads a reply. The reply may name **one command from a short allowlist that
lives in the hub, not in the lab**. The hub maps the name to a fixed local
script; anything it does not recognise is ignored and logged.

- It uses the grant that already exists, `hub → collector:8443`. No new grant,
  no new port, no new direction.
- The collector never initiates anything. If it is compromised, the worst it
  can do is name a command from a list it does not control, which the hub will
  then refuse or perform under its own guards.
- The lab can *ask*. Only the house can *act*. That is the property worth
  demonstrating, and it is the same shape as the telemetry: the trusted side
  moves the data.

### The allowlist, kept short on purpose

**Decided: one entry.** The light clean of the cat area, and nothing else — not
even pause or return-to-dock, unless the household session judges a stop
necessary for safety. A list of one is not a limitation of the design; it is
the design. Every extra name is a thing a compromised collector could ask for.

**Never exposed:** whole-map start (the vendor's `start` cleans everything, a
trap recorded by the house), any setting, do-not-disturb, child lock,
auto-empty, map deletion, and the raw passthrough. A command that changes
configuration, or that cannot be reasoned about, does not belong on a list
whose whole purpose is that a stranger could read it and shrug.

### Guards, evaluated by the hub before it acts

The cat is not at the station; the robot is docked, for a start; battery above
a floor; outside quiet hours; and at most a few starts a day. The hub reports
what it did on the next telemetry push — accepted, or refused with the reason —
so the lab learns the outcome without being trusted with the decision.

## Costs, stated

- **A command waits**: up to one tick, plus about 20 seconds of vendor cloud.
  This is not a remote control, and should never be presented as one.
- **A failed poll logs an error** on the hub, exactly like a failed push does.
- **The house pays for the lab's demonstration**: noise, a robot in the cat's
  area, and possible false detections on the pet camera while it works there.
- **It adds one call and one automation** on the hub — a reload, no restart.

## Telemetry, if this is built

Push the same way the temperature does: state, battery, task and dock status,
errors, cleaning area and time, consumables. **Never** the map image, the
robot's coordinates, or the network details — a floor plan and a position
inside the flat are exactly the kind of thing a public evidence page must not
carry, and the lab has no use for them.

## What the lab side actually does, as built

`GET /command` on the collector's ingest port answers `{}`, or one queued name
and an id. It is handed over **once**: the next ask gets `{}` again, so a lost
reply loses the command instead of repeating it — the safer way round for a
machine that moves. An operator queues one with
[`collector/ask.sh`](../../collector/ask.sh), which writes a file next to the
readings; it commands nothing, it leaves a name where the hub will look.

Measured after deploying it: from an operator's laptop — a member device — that
URL gets no answer at all, because no grant admits it. Only the hub's role may
ask. The control for that measurement is the hub's own UI, which the same
laptop opens.

## What the owner decided

1. **Yes**, the vacuum becomes the lab's mobile unit.
2. **One command**: the light clean of the cat area. Quiet hours to match the
   robot's own, unless the household session knows better.
3. **Refusals may be published as counts** — how many were asked for, how many
   the house refused, and why. No timestamps and no sequence: a count says the
   guard works, a timeline says when the cat eats and when the flat is empty.

## What remains open

1. Whether the vacuum becomes a lab unit at all.
2. The allowlist, and the quiet hours.
3. Whether the outcome of a refused command is published on the evidence page,
   which would be the most interesting part to a reader and says something
   about the household's routine.

The hub side: the exact entity ids, whether a stop belongs on the list after
all, the daily cap, and the shape of the response variable on this version of
the hub. Those are the household session's to correct, and the owner's to
approve there — the same order as every other change that touches the house.

---

## The hub side, drafted

Facts below were read from the hub by the household session; the guard values
are its conservative proposal. The command names are the lab's vocabulary and
mean nothing until the hub maps them, which is the point.

**Two helpers**, created without a restart: `input_text.zt_lab_last_command_id`
(so a repeated id is ignored) and `counter.zt_lab_vacuum_starts` (the daily
cap, reset at midnight).

```yaml
# configuration.yaml, alongside the existing rest_command block
  zt_lab_ask_command:
    url: !secret zt_collector_command_url
    method: GET
    timeout: 5

  zt_lab_push_command_result:
    url: !secret zt_collector_ingest_url
    method: POST
    content_type: "application/json"
    timeout: 5
    payload: >-
      {"sensor":"vacuum_command","value":{{ (result == 'accepted') | int }},
       "id":{{ id | tojson }},"command":{{ command | tojson }},
       "result":{{ result | tojson }},"ts":"{{ now().isoformat() }}"}

  zt_lab_push_vacuum:
    url: !secret zt_collector_ingest_url
    method: POST
    content_type: "application/json"
    timeout: 5
    payload: >-
      {"sensor":"vacuum","value":{{ states('sensor.eufy_ae_c10_battery') | float(0) | tojson }},
       "state":{{ states('vacuum.eufy_ae_c10') | tojson }},
       "task_status":{{ states('sensor.eufy_ae_c10_task_status') | tojson }},
       "dock_status":{{ states('sensor.eufy_ae_c10_dock_status') | tojson }},
       "error":{{ states('sensor.eufy_ae_c10_error_message') | tojson }},
       "cleaning_area":{{ state_attr('vacuum.eufy_ae_c10','cleaning_area') | tojson }},
       "cleaning_time":{{ state_attr('vacuum.eufy_ae_c10','cleaning_time') | tojson }},
       "ts":"{{ now().isoformat() }}"}
```

```yaml
# automations.yaml -- the ask
- id: zt_lab_vacuum_ask
  alias: "zero-trust-lab: ask the collector for a command"
  description: "Lab mobile-unit channel. The allowlist and every guard are here, not in the lab."
  mode: single
  triggers:
    - trigger: time_pattern
      minutes: "/5"
  actions:
    - action: rest_command.zt_lab_ask_command
      response_variable: reply
      continue_on_error: true
    - variables:
        body: "{{ reply.content if reply is defined and reply.content is mapping else {} }}"
        cmd: "{{ body.command | default('', true) }}"
        cmd_id: "{{ body.id | default('', true) }}"
        reason: >-
          {% if is_state('binary_sensor.cat_cam_cat_occupancy','on') %}cat_at_station
          {% elif not is_state('vacuum.eufy_ae_c10','docked') %}not_docked
          {% elif states('sensor.eufy_ae_c10_battery') | float(0) < 50 %}battery
          {% elif states('sensor.eufy_ae_c10_error_message') not in ['','unknown','None'] %}robot_error
          {% elif not (9 <= now().hour < 20) %}quiet_hours
          {% elif states('counter.zt_lab_vacuum_starts') | int(0) >= 2 %}daily_cap
          {% else %}occupancy_settling{% endif %}
    - condition: template
      value_template: "{{ cmd != '' and cmd_id != states('input_text.zt_lab_last_command_id') }}"
    - action: input_text.set_value
      target: {entity_id: input_text.zt_lab_last_command_id}
      data: {value: "{{ cmd_id }}"}
    - choose:
        - conditions: "{{ cmd == 'pet_litter_light' }}"
          sequence:
            - choose:
                - conditions:
                    - condition: state
                      entity_id: binary_sensor.cat_cam_cat_occupancy
                      state: "off"
                      for: "00:10:00"
                    - condition: state
                      entity_id: vacuum.eufy_ae_c10
                      state: "docked"
                    - condition: numeric_state
                      entity_id: sensor.eufy_ae_c10_battery
                      above: 49
                    - condition: template
                      value_template: "{{ states('sensor.eufy_ae_c10_error_message') in ['','unknown','None'] }}"
                    - condition: time
                      after: "09:00:00"
                      before: "20:00:00"
                    - condition: numeric_state
                      entity_id: counter.zt_lab_vacuum_starts
                      below: 2
                  sequence:
                    - action: script.vacuum_pet_litter
                    - action: counter.increment
                      target: {entity_id: counter.zt_lab_vacuum_starts}
                    - action: rest_command.zt_lab_push_command_result
                      data: {id: "{{ cmd_id }}", command: "{{ cmd }}", result: accepted}
              default:
                - action: rest_command.zt_lab_push_command_result
                  data: {id: "{{ cmd_id }}", command: "{{ cmd }}", result: "refused:{{ reason }}"}
      default:
        - action: rest_command.zt_lab_push_command_result
          data: {id: "{{ cmd_id }}", command: "{{ cmd }}", result: "refused:unknown_command"}

# the daily cap resets with the day
- id: zt_lab_vacuum_cap_reset
  alias: "zero-trust-lab: reset the lab daily vacuum cap"
  mode: single
  triggers:
    - trigger: time
      at: "00:00:00"
  actions:
    - action: counter.reset
      target: {entity_id: counter.zt_lab_vacuum_starts}

# telemetry, the same push pattern as the temperature
- id: zt_lab_push_vacuum
  alias: "zero-trust-lab: push vacuum state to collector"
  mode: single
  triggers:
    - trigger: state
      entity_id:
        - vacuum.eufy_ae_c10
        - sensor.eufy_ae_c10_task_status
        - sensor.eufy_ae_c10_error_message
        - sensor.eufy_ae_c10_dock_status
      to: ~
    - trigger: time_pattern
      minutes: "/5"
  actions:
    - action: rest_command.zt_lab_push_vacuum
      continue_on_error: true
```

Never pushed: the map image, the robot's coordinates, and the network details.
A floor plan and a position inside the flat have no place on a public page.

### Delivery: at most once, on purpose

The collector hands a command over as it is served and forgets it. If the
reply is lost, the command is lost and the operator queues it again; the
alternative -- keep serving until acknowledged -- turns a lost acknowledgement
into a second clean. The hub's memory of the last id stays as a second belt:
two mechanisms, both cheap, and the failure mode of each is that nothing moves.

### Still the owner's, not mine to widen

The household session proposes four names: the cat-area light clean, a
front-door clean, pause, and return to dock. The owner named **one**. Pause and
return to dock only ever stop a machine that is already moving, so they are put
to him as safety rather than as scope; the front-door clean is scope, and stays
off the list unless he says otherwise.
