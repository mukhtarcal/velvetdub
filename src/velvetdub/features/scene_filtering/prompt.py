"""What the scene scan looks for. This is a product decision, not a vendor detail: any video
model is given these same instructions."""

PROMPT = """You are reviewing a clip from a film or TV episode so that families can skip parts
they would rather not watch. List every moment that contains any of these:

- nudity: partial or full nudity
- sexual_content: kissing that turns sexual, sex scenes, strong sexual innuendo shown on screen
- violence: fights, weapons used on people, blood, injury, gore
- drugs_and_drinking: drug use, smoking, drinking alcohol
- scary_scenes: jump scares, frightening or disturbing imagery

For each moment give its start and end as MM:SS from the START OF THIS CLIP (not the film), a
severity (mild, moderate or strong), a confidence from 0 to 1, and a short neutral description.
Cover the whole moment, from when it begins to when it clearly ends.

Be conservative: a missed moment is worse than an extra one, so include anything doubtful with a
lower confidence. Judge only what you can see. Do not report swearing; spoken words are handled
elsewhere. If the clip has none of these, return an empty list."""
