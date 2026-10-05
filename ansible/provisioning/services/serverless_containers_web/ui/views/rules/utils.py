

def jsonBooleanToHumanReadable(jsonBoolExpr):
    boolString = ""
    boolOperators = ['and','or','==','>=','<=','<','>','+','-','*','/']
    unaryOperators = {'!': 'NOT ', '!!': ''}

    ## Check if dict or literal
    if type(jsonBoolExpr) is dict:
        firstElement = list(jsonBoolExpr.keys())[0]
    else:
        firstElement = jsonBoolExpr


    if firstElement in boolOperators:
        ## Got bool expression
        jsonBoolValues = jsonBoolExpr[firstElement]
        for i in range(0, len(jsonBoolValues)):
            boolString += jsonBooleanToHumanReadable(jsonBoolValues[i])
            if i < len(jsonBoolValues) - 1:
                boolString += " " + firstElement.upper() + " "

    elif firstElement in unaryOperators:
        ## Got unary expression (e.g., {"!": [{"var": "cpu.structure.cpu.lent"}]})
        operand = jsonBoolExpr[firstElement]
        operand = operand[0] if isinstance(operand, list) else operand
        boolString = unaryOperators[firstElement] + jsonBooleanToHumanReadable(operand)

    elif firstElement == 'var':
        ## Got variable
        boolString = jsonBoolExpr[firstElement]

    else:
        ## Got literal
        boolString = str(firstElement)

    return boolString


def getRulesResources(data):
    resources = set()
    for item in data:
        resources.add(item['resource'])

    return list(resources)