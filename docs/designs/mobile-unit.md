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

## The hub side, reviewed

The first draft was written from the household session's facts; it reviewed it
against the hub and corrected six things. The corrections are the interesting
part, so they are kept here rather than quietly folded in.

**A safety gap I had missed.** One command, handed over once, still lets an
operator queue it again every five minutes: the robot would clean the cat's
area, dock, and set off again, all day. My draft counted starts in a helper.
The house's answer is better and needs no helper: require the vacuum to have
been **docked, unchanged, for three hours**. That caps lab starts at about four
a day inside the window, refuses a lab start stacking on a clean the household
just ran, and refuses automatically when the vendor cloud flaps — because an
`unavailable` resets the clock.

**The failure I wrote in.** My template read `reply.content` unguarded. When
the poll times out, `continue_on_error` lets the run continue and the variable
is never set, so the automation would have failed every five minutes for as
long as the collector was down — turning our outage into their noise. It now
checks `reply is defined and reply.status == 200 and reply.content is mapping`.

**Do not call the household's script.** I had reused `script.vacuum_pet_litter`,
which is the button in the house's own app. It has been repointed once already,
and if it is repointed again the lab's command silently becomes something else.
The corrected version selects the scenario itself, matched by name prefix, and
refuses with `no_scenario` if the option is missing.

**Waiting long enough to mean it.** "Accepted" only meant the hub pressed a
button in the vendor's cloud. It now waits up to 90 seconds for the vacuum to
report `cleaning` and answers `started` or `sent_no_start`.

**Two small ones:** the poll runs at second 30 so it never shares an instant
with the temperature push, and the automation is `max_exceeded: silent`.

**Stops are not needed after all.** I was going to put pause and return-to-dock
to the owner as safety. The house already keeps its own stops — the vendor app
and the wall tablet — so adding them to the lab's list buys nothing and widens
it. The allowlist stays at one command.

**What may be published.** Three counts only: started, refused by a house
guard, and not on the allowlist. The per-guard reasons stay in the collector's
own log: published over time, a `cat_not_clear` count is a count of how often
the cat was at his bowls, which is the household's business and not the
reader's.

### The corrected draft, as it will be applied

Reviewed against the hub by the household session, which applies it after the
owner approves there. The one allowed command and every guard live in this
file, on the hub — not in the lab.

```yaml
# secrets.yaml
zt_collector_command_url: "http://<collector tailnet address>/command"

# configuration.yaml, under the existing rest_command block
  zt_lab_ask_command:
    url: !secret zt_collector_command_url
    method: GET
    timeout: 5

  zt_lab_push_command_outcome:
    url: !secret zt_collector_ingest_url
    method: POST
    content_type: "application/json"
    timeout: 5
    payload: >-
      {"sensor":"vacuum_command_outcome","value":{{ outcome | tojson }},
       "reason":{{ reason | tojson }},"id":{{ id | tojson }},
       "ts":"{{ now().isoformat() }}"}
```

```yaml
# automations.yaml
- id: zt_lab_vacuum_ask
  alias: "zero-trust-lab: ask the collector for a vacuum command"
  description: "Lab mobile-unit channel. The hub asks; the one allowed command and every guard live here, not in the lab."
  mode: single
  max_exceeded: silent
  triggers:
    - trigger: time_pattern
      minutes: "/5"
      seconds: 30
  actions:
    - action: rest_command.zt_lab_ask_command
      response_variable: reply
      continue_on_error: true
    - variables:
        body: "{{ reply.content if (reply is defined and reply.status == 200 and reply.content is mapping) else {} }}"
        cmd: "{{ body.command | default('', true) }}"
        cmd_id: "{{ body.id | default('', true) }}"
    - condition: template
      value_template: "{{ cmd != '' }}"
    - variables:
        reason: >-
          {%- set occ = states.binary_sensor.cat_cam_cat_occupancy -%}
          {%- set vac = states.vacuum.eufy_ae_c10 -%}
          {%- set opts = state_attr('select.eufy_ae_c10_scene_task','options') | default([], true) | select('search','^Pet Litter Light') | list -%}
          {%- if cmd != 'pet_area_light' -%}not_allowlisted
          {%- elif occ is none or occ.state != 'off' or (now() - occ.last_changed).total_seconds() < 600 -%}cat_not_clear
          {%- elif vac is none or vac.state != 'docked' -%}not_docked
          {%- elif (now() - vac.last_changed).total_seconds() < 10800 -%}cooldown
          {%- elif states('sensor.eufy_ae_c10_battery') | float(0) < 50 -%}battery
          {%- elif states('sensor.eufy_ae_c10_error_message') not in ['', 'unknown'] -%}robot_error
          {%- elif not (today_at('08:00') <= now() < today_at('20:30')) -%}quiet_hours
          {%- elif opts | count == 0 -%}no_scenario
          {%- else -%}ok{%- endif -%}
    - if:
        - condition: template
          value_template: "{{ reason == 'ok' }}"
      then:
        - action: select.select_option
          target:
            entity_id: select.eufy_ae_c10_scene_task
          data:
            option: "{{ state_attr('select.eufy_ae_c10_scene_task','options') | select('search','^Pet Litter Light') | list | first }}"
        - wait_for_trigger:
            - trigger: state
              entity_id: vacuum.eufy_ae_c10
              to: cleaning
          timeout: "00:01:30"
          continue_on_timeout: true
        - action: rest_command.zt_lab_push_command_outcome
          data:
            outcome: "{{ 'started' if wait.trigger else 'sent_no_start' }}"
            reason: ""
            id: "{{ cmd_id }}"
          continue_on_error: true
      else:
        - action: rest_command.zt_lab_push_command_outcome
          data:
            outcome: refused
            reason: "{{ reason }}"
            id: "{{ cmd_id }}"
          continue_on_error: true
```

The guards, in words: the cat has been out of frame for ten minutes and the
sensor is not merely unavailable; the vacuum is docked and has been for three
hours; the battery is at least half; the robot reports no error; the local time
is between 08:00 and 20:30, so a ten-to-fifteen minute clean finishes before
the robot's own quiet hours begin; and the scenario still exists under the name
the automation matches.

Telemetry — state, battery, task and dock status, errors, cleaning area and
time, consumables — is pushed the same way the temperature is. Never pushed:
the map image, the robot's coordinates, the network details. A floor plan and a
position inside the flat have no place on a public page.

### The order the first commands run in

1. An idle poll returns `{}`, and the household session confirms the response
   shape from the hub's own trace.
2. An unknown name: refused, `not_allowlisted`. Nothing moves.
3. The real name at a moment a guard is certain to fail — after 20:30, so
   `quiet_hours`. Nothing moves.
4. Only then a real start, in hours, with the household told first, and the
   camera-watching session warned that the robot will be in frame.

Refusals before motion is the right order, and it is the household session's
condition, not a courtesy.

### Delivery: at most once, on purpose

The collector hands a command over as it is served and forgets it. If the
reply is lost, the command is lost and the operator queues it again; the
alternative -- keep serving until acknowledged -- turns a lost acknowledgement
into a second clean. The hub's memory of the last id stays as a second belt:
two mechanisms, both cheap, and the failure mode of each is that nothing moves.

### One command, settled

The household session first proposed four names; the owner named one. The stops
turned out to be unnecessary — the house keeps its own, in the vendor's app and
on the wall tablet — so the list stays at the cat-area light clean, and every
other name is answered `not_allowlisted` without anything moving.
