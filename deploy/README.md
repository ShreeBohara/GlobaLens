# deploy

What production runs. `prod.lock` names the image digests and the site commit that are approved
for production; merging the bot's pull request that changes it is the owner's approval, and the
pull deployer on the node follows it. `compose/node-paid/` holds the node's Compose stack.

Placeholder. `compose/node-paid/` arrives with P1 task 7 and `prod.lock` with P1 task 16.
