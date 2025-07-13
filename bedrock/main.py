#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create an Amazon Bedrock Guardrail, attach it to a new Agent, prepare the
Agent, and invoke it – all with plain boto3 calls.

© 2025 Amazon.com, Inc. or its affiliates. SPDX-License-Identifier: Apache-2.0
"""

def create_role(guardrail_id):

    # ─── edit these ────────────────────────────────────────────────────────────────
    ROLE_NAME      = "BedrockAgentExecutionRole"
    GUARDRAIL_ID   = guardrail_id        # or "*" to trust all guardrails
    # ──────────────────────────────────────────────────────────────────────────────

    guardrail_arn  = f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:guardrail/{GUARDRAIL_ID}"
    model_arn = f"arn:aws:bedrock:{REGION}::foundation-model/{FOUNDATION_MODEL}"

    iam = boto3.client("iam")

    # 1 ─── service-trust policy (Bedrock must be able to assume the role) ─────────
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": { "Service": "bedrock.amazonaws.com" },
            "Action":   "sts:AssumeRole",
            "Condition": {        # tighten the scope once the agent exists
                "StringEquals": { "aws:SourceAccount": ACCOUNT_ID },
                "ArnLike":      { "AWS:SourceArn": f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:agent/*" }
            }
        }]
    }

    # 2 ─── permissions Bedrock needs during inference + guardrails ────────────────
    perm_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {   # call foundation models
                "Sid": "InvokeFoundationModels",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                "Resource": model_arn
            },
            {   # apply your guardrail(s)
                "Sid": "ApplyGuardrail",
                "Effect": "Allow",
                "Action": "bedrock:ApplyGuardrail",
                "Resource": guardrail_arn
            }
        ]
    }

    # 3 ─── create the role & attach the inline policy ─────────────────────────────
    role = iam.create_role(
        RoleName               = ROLE_NAME,
        AssumeRolePolicyDocument= json.dumps(trust_policy),
        Description            = "Executes Amazon Bedrock agents with guardrails applied",
        Tags=[{"Key": "CreatedBy", "Value": "script"}]
    )

    iam.put_role_policy(
        RoleName      = ROLE_NAME,
        PolicyName    = "BedrockAgentPermissions",
        PolicyDocument= json.dumps(perm_policy)
    )

    # 4 ─── wait a few seconds for IAM to propagate, then print the ARN ────────────
    time.sleep(10)           # <-- simpler than building a waiter for this demo
    print("✅ Role ready →", role["Role"]["Arn"])



import json
import time
import uuid
import boto3
import textwrap
from botocore.exceptions import ClientError, WaiterError
from dotenv import load_dotenv
import sys

load_dotenv()

# ---------------------------------------------------------------------------
# 0.  Configuration – edit these!
# ---------------------------------------------------------------------------

REGION            = "us-east-1"   # e.g. "us-east-1"
FOUNDATION_MODEL  = "anthropic.claude-3-haiku-20240307-v1:0"   # e.g. "meta.llama3-8b-instruct-v1:0"
#AGENT_ROLE_ARN    = "arn:aws:iam::637423356581:role/service-role/AmazonBedrockExecutionRoleForAgents_T1BZO63F7ZS"   # IAM role the Agent will assume
ACCOUNT_ID        = "637423356581"   # just for naming hygiene
AGENT_ROLE_ARN = "arn:aws:iam::637423356581:role/BedrockAgentExecutionRole"

# ---------------------------------------------------------------------------
# 1.  Create a guardrail (status = DRAFT)
#     See Bedrock.create_guardrail docs :contentReference[oaicite:0]{index=0}
# ---------------------------------------------------------------------------

def create_guardrail():
    """
    Create a guardrail.
    :return: the guardrail ID and version
    :rtype: tuple[str, str]
    """
    br = boto3.client("bedrock")


    guardrail_name = f"demo-guardrail-{uuid.uuid4().hex[:8]}"
    print(f"Creating Guardrail: {guardrail_name}")

    guardrail_resp = br.create_guardrail(
        name        = guardrail_name,
        description = "Blocks any mention of heavy-metal music.",
        topicPolicyConfig = {
            "topicsConfig": [
                {
                    "name"       : "Heavy metal",
                    "type"       : "DENY",
                    "definition": "Heavy metal is a style of rock music that features lyrics exploring the darker corners of human experience—mythology, rebellion, social alienation, war, the occult",
                    "examples"   : ["Create a playlist of heavy metal songs."]
                }
            ]
        },
        contentPolicyConfig={
            'filtersConfig': [
                {
                    'type': 'HATE',
                    'inputStrength': 'HIGH',
                    'outputStrength': 'HIGH',
                    'inputModalities': [
                        'TEXT','IMAGE',
                    ],
                    'outputModalities': [
                        'TEXT','IMAGE',
                    ],
                    'inputAction': 'BLOCK', # ? if none we can see the This allows you to preview the guardrail evaluation and see that VIOLENCE was detected (true), but no action was taken because you configured that to NONE.
                    'outputAction': 'BLOCK',
                    'inputEnabled': True, # YOU ARE CHARGE FOR EVALUATION BUT SEE WHAT THE GUARDRAIL OUTPUTS
                    'outputEnabled': True
                },
                {
                    'type': 'PROMPT_ATTACK',
                    'inputStrength': 'HIGH',
                    'outputStrength': 'NONE', # FOR PROMPT ATTACKS WE CAN ONLY BLOCK INPUTS
                    'inputModalities': [
                        'TEXT','IMAGE'
                    ],
                    'outputModalities': [
                        'TEXT','IMAGE',
                    ],
                    'inputAction': 'BLOCK',
                    'outputAction': 'BLOCK',
                    'inputEnabled': True,
                    'outputEnabled': True
                }
            ]
        },
        wordPolicyConfig={
            'wordsConfig': [
                {
                    'text': 'metal',   #HERE WE CAN ONLY 
                    'inputAction': 'BLOCK',
                    'outputAction': 'BLOCK',
                    'inputEnabled': True,
                    'outputEnabled': True
                },
                {
                    'text': 'rock music',   #HERE WE CAN ONLY 
                    'inputAction': 'BLOCK',
                    'outputAction': 'BLOCK',
                    'inputEnabled': True,
                    'outputEnabled': True
                },
            ],
            'managedWordListsConfig': [
                {
                    'type': 'PROFANITY',# BLOCK PROFANITE WORDS
                    'inputAction': 'BLOCK',
                    'outputAction': 'BLOCK',
                    'inputEnabled': True,
                    'outputEnabled': True
                },
            ]
        },
        sensitiveInformationPolicyConfig={
            'piiEntitiesConfig': [
                {
                    'type': 'CREDIT_DEBIT_CARD_NUMBER',
                    'action': 'BLOCK',
                    'inputAction': 'BLOCK',
                    'outputAction': 'BLOCK',
                    'inputEnabled': True,
                    'outputEnabled': True
                },
                {
                    'type': 'EMAIL',
                    'action': 'ANONYMIZE',
                    'inputAction': 'ANONYMIZE',
                    'outputAction': 'ANONYMIZE',
                    'inputEnabled': True,
                    'outputEnabled': True
                }
            ],
            'regexesConfig': [
                {
                    'name': 'BITCOIN_WALLET',
                    'description': 'Bitcoin address (Base58 or Bech32)',
                    'pattern': r"\b(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[0-9a-z]{6,87})\b", # 1BoatSLRHtKNngkdXEeobR76b53LETtpyT
                    'action': 'ANONYMIZE',
                    'inputAction': 'ANONYMIZE', 
                    'outputAction': 'ANONYMIZE',
                    'inputEnabled': True,
                    'outputEnabled': True
                },
            ]
        },
        contextualGroundingPolicyConfig={
            'filtersConfig': [
                {
                    'type': 'GROUNDING',
                    'threshold': 0.8, # The filtering threshold determines the minimum allowable confidence score for the model response to be considered as grounded
                    'action': 'BLOCK',
                    'enabled': True
                },
                {
                    'type': 'RELEVANCE',
                    'threshold': 0.5, # The filtering threshold determines the minimum allowable confidence score for the model response to be considered as grounded
                    'action': 'BLOCK',
                    'enabled': True
                },
            ]
        },
        blockedInputMessaging   = "Sorry, I can't answer questions about heavy-metal music.",
        blockedOutputsMessaging = "Sorry—my answer mentioned heavy-metal music, so I had to block it."
    )
    guardrail_id      = guardrail_resp["guardrailId"]          # something like "gr-abc123..."
    guardrail_version = guardrail_resp["version"]              # always "DRAFT" at creation
    print(f"Guardrail ID: {guardrail_id} (version={guardrail_version})") # Guardrail ID: a6w0gl4ttetz (version=DRAFT)
    
    return guardrail_id, guardrail_version

"""

################################################
#   1.5 call create_guardrail with the guardrail id which returns an agent role arn
#  #create_role(guardrail_id="k6582ey6du0o")
######################################

# OPTIONAL: snapshot the guardrail so you have an immutable version = "1"
# br.create_guardrail_version(guardrailIdentifier=guardrail_id,
#                             description="Initial production snapshot")

# ---------------------------------------------------------------------------
# 2.  Create an Agent and attach the guardrail
#     GuardrailConfiguration documented in CreateAgent :contentReference[oaicite:1]{index=1}
# ---------------------------------------------------------------------------

"""
guardrail_id      = "k6582ey6du0o"  # replace with your guardrail ID
guardrail_version = "DRAFT"          # or "1" if you snapshot the guardrail

agent_name = f"demo-agent-guardrails-{uuid.uuid4().hex[:6]}" # demo-guarded-agent-162c24
ag = boto3.client("bedrock-agent")

print(f"Creating Agent: {agent_name}")
agent_resp = ag.create_agent(
    agentName            = agent_name,
    foundationModel      = FOUNDATION_MODEL,
    instruction          = "You are a friendly music bot.  Obey the guardrail.",
    agentResourceRoleArn = AGENT_ROLE_ARN,
    guardrailConfiguration = {
        "guardrailIdentifier": guardrail_id,
        "guardrailVersion"   : guardrail_version        # "DRAFT" or "1" if you snapshotted
    },
    idleSessionTTLInSeconds = 300                       # keep chat context for 5 minutes
)
agent_id = agent_resp["agent"]["agentId"]
print(f"Agent ID: {agent_id}") # Agent ID: 5NCM7AF2D1

"""

# ---------------------------------------------------------------------------
# 3.  Prepare the Agent so it can serve traffic  :contentReference[oaicite:2]{index=2}
# ---------------------------------------------------------------------------


"""

print("Preparing Agent (this creates a DRAFT version and loads the model) …")
agent_id = "XPPGNLJAJV" 
ag = boto3.client("bedrock-agent")
ag.prepare_agent(agentId=agent_id)

# Poll until the Agent shows status PREPARED (no waiter yet in boto3)
while True:
    status = ag.get_agent(agentId=agent_id)["agent"]["agentStatus"]
    print("   status =", status)
    if status == "PREPARED":
        break
    if status == "FAILED":
        raise RuntimeError("Agent failed to prepare; check failureReasons.")
    time.sleep(15)

print("Agent is ready!")

"""

# ---------------------------------------------------------------------------
# 3.5.  Create an Agent Version or Alias
#     
# ---------------------------------------------------------------------------

# --- Freeze the draft into version 1 -------------------------------

"""
agent_id = "XPPGNLJAJV" 
ag = boto3.client("bedrock-agent")

    # e.g. "1"

# --- Create an alias that sends 100 % traffic to v1 ----------------

alias_resp     = ag.create_agent_alias(            # :contentReference[oaicite:2]{index=2}
    agentId=agent_id,
    agentAliasName="demo"
)
agent_alias_id = alias_resp["agentAlias"]["agentAliasId"]






# (optional) wait until aliasStatus == "PREPARED"
while ag.get_agent_alias(agentId=agent_id,
                         agentAliasId=agent_alias_id)["agentAlias"]["agentAliasStatus"] != "PREPARED":
    time.sleep(5)

agent_response = ag.get_agent_alias(agentId=agent_id,
                         agentAliasId=agent_alias_id)

print(f"Agent alias with id {agent_alias_id} is ready pointing to version {agent_response['agentAlias']['routingConfiguration'][0]["agentVersion"]}")


"""

# ---------------------------------------------------------------------------
# 4.  Invoke the Agent at runtime
#     Agents for Bedrock Runtime → invoke_agent :contentReference[oaicite:3]{index=3}
# ---------------------------------------------------------------------------
def check_grounding_and_relevance(guardrail_id,guardrail_version):

    runtime = boto3.client("bedrock-runtime", region_name=REGION)

    SOURCE = """
    Paris is the capital of France.
    Berlin is the capital of Germany.
    """

    QUESTION = "What is the capital of Germany?"

    ANSWERS = {
        "grounded"   : "Berlin is the capital of Germany.",   # should PASS
        "hallucinate": "The capital of Germany is Munich."    # should BLOCK
    }

    def check(answer):
        resp = runtime.apply_guardrail(
            guardrailIdentifier = guardrail_id,
            guardrailVersion    = guardrail_version,
            source   = "OUTPUT",          # we are validating a *response*
            outputScope = "FULL",         # ask for the full trace  :contentReference[oaicite:0]{index=0}
            content  = [
                {"text": {"text": SOURCE,   "qualifiers": ["grounding_source"]}},
                {"text": {"text": QUESTION, "qualifiers": ["query"]}},
                {"text": {"text": answer,   "qualifiers": ["guard_content"]}},
            ],
        )

        cg = resp["assessments"][0]["contextualGroundingPolicy"]["filters"]
        print(cg)
        g_score = cg[0]["score"]
        r_score = cg[1]["score"]
        action  = resp["action"]
        print(textwrap.dedent(f"""
            answer      : {answer}
            action      : {action}
            grounding   : {g_score:.3f}
            relevance   : {r_score:.3f}
        """))

    for label, ans in ANSWERS.items():
        check(ans)


def show_guardrail_trace(trace_part: dict):
    
    g = trace_part["trace"]["guardrailTrace"]       # ← object of interest
    print(g)
    print("\n── GuardrailTrace ──")
    print("overall action:", g["action"])           # NONE | GUARDRAIL_INTERVENED

    for side, assessments in (("INPUT",  g.get("inputAssessments",  [])),
                              ("OUTPUT", g.get("outputAssessments", []))):
        for a in assessments:
            print(f"{side}: policy={a}")
            # the assessment object contains sub-sections for every policy type:
            #   topicPolicy, contentPolicy, wordPolicy, sensitiveInformationPolicy …
            # each sub-section lists matches + the action Bedrock took.
            #print(json.dumps(a, indent=2)[:500], "…")   # trim for brevity


# here we invoke th e agennttt
runtime = boto3.client("bedrock-agent-runtime")
agent_id = "XPPGNLJAJV" 
agent_alias_id = "H4O0JQYLDK"  # replace with your agent alias ID

session_id = str(uuid.uuid4())
user_prompt = "what type of music do you like?"
      


response  = runtime.invoke_agent(
    agentId   = agent_id,
    agentAliasId = agent_alias_id,
    sessionId = session_id,
    inputText = user_prompt,
    enableTrace     = True,    
    streamingConfigurations = {
        "applyGuardrailInterval": 20,               # re-check every 20 chars (default 50)
        "streamFinalResponse":   False,

    }
)

completion_text = ""

for event in response["completion"]:
    if "chunk" in event:                              # response text
        sys.stdout.write(event["chunk"]["bytes"].decode())
        sys.stdout.flush()

    if "trace" in event:                              # a TracePart object
        trace_part = event["trace"]                   # contains .trace sub-object
        if "guardrailTrace" in trace_part.get("trace", {}):
            show_guardrail_trace(trace_part)
     




"""
runtime = boto3.client("bedrock-agent-runtime")
agent_id = "XPPGNLJAJV" 
agent_alias_id = "H4O0JQYLDK"  # replace with your agent alias ID

session_id = str(uuid.uuid4())
user_prompt = "I hate ugly people"

response  = runtime.invoke_agent(
    agentId   = agent_id,
    agentAliasId = agent_alias_id,
    sessionId = session_id,
    inputText = user_prompt
)
traces = []
completion = ""
#print(response)
pretty_trace(response)  # print the guardrail action and assessments

for event in response.get("completion"):
    print(event)
    try:
        trace = event["trace"]
        traces.append(trace['trace'])
    except KeyError:
        chunk = event["chunk"]
        completion = completion + chunk["bytes"].decode()
    except Exception as e:
        print(e)
    
    print(traces)
    print(completion)
   #json.dumps(completion)

"""



""" 

for event in resp_stream["completion"]:
    if "chunk" in event:                         # plain response tokens
        sys.stdout.write(event["chunk"]["bytes"].decode("utf-8"))
        sys.stdout.flush()
    elif "trace" in event:                       # a reasoning step
        print("\n\n--- TRACE ----------------------------------")
        print(event["trace"]["trace"])
        print("--------------------------------------------\n")




payload = invoke_resp["bytes"].decode("utf-8")
answer  = json.loads(payload)

print("\n--- Agent Response -------------------------------------------")
print(json.dumps(answer, indent=2))

if answer.get("stopReason") == "guardrail_intervened":
    print("\nGuardrail blocked the request exactly as intended ✔️")
"""
# ---------------------------------------------------------------------------
# 5.  Clean-up helpers (uncomment if you want to delete resources)
# ---------------------------------------------------------------------------
# ag.delete_agent(agentId=agent_id)
# br.delete_guardrail(guardrailIdentifier=guardrail_id)

