from rasd import AlertDispatcher, ConsoleNotifier, Pipeline, Reading

pipeline = Pipeline(AlertDispatcher([ConsoleNotifier()]))

cases = {
    "S014": Reading(38.2, 115, 85, 85, "غثيان ودوخة وقت الفسحة", age_years=12),
    "S027": Reading(37.9, 96, 91, 91),
    "S042": Reading(36.9, 88, 90, 90, "صداع"),
    "S031": Reading(None, None, 58, 58),
    "S008": Reading(36.7, 84, 93, 93),
}
for code, reading in cases.items():
    result, outcome = pipeline.process(code, reading)
    print(f"--- {code}: {result.label_ar} / {outcome.value}\n")
