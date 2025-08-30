
import json
import time
import uuid
import boto3
import textwrap
from dotenv import load_dotenv
import sys
import config as cfg
import os 

load_dotenv()

# Configuration
FOUNDATION_MODEL  = cfg.FOUNDATION_MODEL
ACCOUNT_ID   = os.getenv("ACCOUNT_ID")
REGION = cfg.REGION


def create_role(guardrail_id, role_name="BedrockAgentExecutionRole"):

    guardrail_arn  = f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:guardrail/{guardrail_id}"
    model_arn = f"arn:aws:bedrock:{REGION}::foundation-model/{FOUNDATION_MODEL}"

    iam = boto3.client("iam")

    # Service-trust policy (Bedrock must be able to assume the role) 
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

    # Permissions Bedrock needs during inference + guardrails 
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

    # Create the role & attach the inline policy 
    role = iam.create_role(
        RoleName               = role_name,
        AssumeRolePolicyDocument= json.dumps(trust_policy),
        Description            = "Executes Amazon Bedrock agents with guardrails applied",
        Tags=[{"Key": "CreatedBy", "Value": "script"}]
    )

    iam.put_role_policy(
        RoleName      = role_name,
        PolicyName    = "BedrockAgentPermissions",
        PolicyDocument= json.dumps(perm_policy)
    )

    # Wit a few seconds for IAM to propagate, then print the ARN 
    time.sleep(10) 
    print("✅ Role ready →", role["Role"]["Arn"])
    return role["Role"]["Arn"]  

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
                    'inputAction': 'BLOCK', 
                    'outputAction': 'BLOCK',
                    'inputEnabled': True, 
                    'outputEnabled': True
                },
                {
                    'type': 'PROMPT_ATTACK',
                    'inputStrength': 'HIGH',
                    'outputStrength': 'NONE', 
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
                    'text': 'metal',  
                    'inputAction': 'BLOCK',
                    'outputAction': 'BLOCK',
                    'inputEnabled': True,
                    'outputEnabled': True
                },
                {
                    'text': 'rock music',  
                    'inputAction': 'BLOCK',
                    'outputAction': 'BLOCK',
                    'inputEnabled': True,
                    'outputEnabled': True
                },
            ],
            'managedWordListsConfig': [
                {
                    'type': 'PROFANITY',
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
                    'pattern': r"\b(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[0-9a-z]{6,87})\b", 
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

def create_agent(guardrail_id, agent_role_arn, guardrail_version = "DRAFT" ):

    agent_name = f"demo-agent-guardrails-{uuid.uuid4().hex[:6]}" # demo-guarded-agent-162c24
    ag = boto3.client("bedrock-agent")

    print(f"Creating Agent: {agent_name}")
    agent_resp = ag.create_agent(
        agentName            = agent_name,
        foundationModel      = FOUNDATION_MODEL,
        instruction          = "You are a friendly music bot.  Obey the guardrail.",
        agentResourceRoleArn = agent_role_arn,
        guardrailConfiguration = {
            "guardrailIdentifier": guardrail_id,
            "guardrailVersion"   : guardrail_version        # "DRAFT" or "1" if you snapshotted
        },
        idleSessionTTLInSeconds = 300                       # keep chat context for 5 minutes
    )
    agent_id = agent_resp["agent"]["agentId"]
    print(f"Agent ID: {agent_id}")
    return agent_id

def prepare_agent(agent_id):
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

def agent_alias(agent_id,alias_name="demo"):
    ag = boto3.client("bedrock-agent")


    alias_resp     = ag.create_agent_alias(         
        agentId=agent_id,
        agentAliasName=alias_name
    )
    agent_alias_id = alias_resp["agentAlias"]["agentAliasId"]

    # Check agent status
    while ag.get_agent_alias(agentId=agent_id,
                            agentAliasId=agent_alias_id)["agentAlias"]["agentAliasStatus"] != "PREPARED":
        time.sleep(5)

    agent_response = ag.get_agent_alias(agentId=agent_id,
                            agentAliasId=agent_alias_id)

    print(f"Agent alias with id {agent_alias_id} is ready pointing to version {agent_response['agentAlias']['routingConfiguration'][0]["agentVersion"]}")
    return agent_alias_id, agent_response['agentAlias']['routingConfiguration'][0]["agentVersion"]

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

    print("GuardrailTrace")
    print("overall action:", g["action"])           # NONE | GUARDRAIL_INTERVENED

    for side, assessments in (("INPUT",  g.get("inputAssessments",  [])),
                              ("OUTPUT", g.get("outputAssessments", []))):
        for a in assessments:
            print(f"{side}: policy={a}")

def invoke_agent(agent_id, agent_alias_id, user_prompt = "what type of music do you like?"):
    runtime = boto3.client("bedrock-agent-runtime")
    session_id = str(uuid.uuid4())

        
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


    for event in response["completion"]:
        if "chunk" in event:                              # response text
            sys.stdout.write(event["chunk"]["bytes"].decode())
            sys.stdout.flush()

        if "trace" in event:                              # a TracePart object
            trace_part = event["trace"]                   # contains .trace sub-object
            if "guardrailTrace" in trace_part.get("trace", {}):
                show_guardrail_trace(trace_part)
     

def main():
    guardrail_id, guardrail_version = create_guardrail()
    role_arn = create_role(guardrail_id=guardrail_id)
    agent_id = create_agent(guardrail_id = guardrail_id, agent_role_arn = role_arn)
    prepare_agent(agent_id = agent_id)
    alias_id, alias_name = agent_alias(agent_id)
    invoke_agent(agent_id = agent_id, agent_alias_id = alias_id, user_prompt = "what type of music do you like?")
    
if __name__ == "__main__":
    main()



