"""Fixed, server-graded prototype questions. Keys never appear in unsubmitted quiz UI."""
import re
from pathlib import Path

TITLE = 'Chemical Equations—From Formulae to Balancing'
LESSON = (Path(__file__).resolve().parents[1] / 'content' / 'chemical_equations.md').read_text(encoding='utf-8')


def coefficient(id, equation, answer, skill, explanation, hint):
    return dict(id=id, prompt=equation, answer=answer, skill=skill, explanation=explanation, hint=hint, type='coefficients')


PRACTICE = [
    coefficient('P1','Mg + O₂ → MgO',(2,1,2),'Diatomic elements','2Mg + O₂ → 2MgO. Mg: 2 = 2; O: 2 = 2.','Oxygen arrives as O₂. Make two MgO units.'),
    coefficient('P2','N₂ + H₂ → NH₃',(1,3,2),'Atom counting','N₂ + 3H₂ → 2NH₃. N: 2 = 2; H: 6 = 6.','Match the two nitrogen atoms first.'),
    coefficient('P3','CH₄ + O₂ → CO₂ + H₂O',(1,2,1,2),'Combustion','CH₄ + 2O₂ → CO₂ + 2H₂O. C: 1 = 1; H: 4 = 4; O: 4 = 2+2.','Balance carbon, then hydrogen, then oxygen.')]

QUIZ = [
    coefficient('Q1','Na + Cl₂ → NaCl',(2,1,2),'Diatomic elements','2Na + Cl₂ → 2NaCl. Na: 2 = 2; Cl: 2 = 2.',''),
    coefficient('Q2','Cu + O₂ → CuO',(2,1,2),'Diatomic elements','2Cu + O₂ → 2CuO. Cu: 2 = 2; O: 2 = 2.',''),
    coefficient('Q3','H₂ + Cl₂ → HCl',(1,1,2),'Atom counting','H₂ + Cl₂ → 2HCl. H: 2 = 2; Cl: 2 = 2.',''),
    coefficient('Q4','Al + O₂ → Al₂O₃',(4,3,2),'Odd/even atom counts','4Al + 3O₂ → 2Al₂O₃. Al: 4 = 4; O: 6 = 6.',''),
    coefficient('Q5','KClO₃ → KCl + O₂',(2,2,3),'Odd/even atom counts','2KClO₃ → 2KCl + 3O₂. K: 2 = 2; Cl: 2 = 2; O: 6 = 6.',''),
    coefficient('Q6','C₂H₆ + O₂ → CO₂ + H₂O',(2,7,4,6),'Combustion','2C₂H₆ + 7O₂ → 4CO₂ + 6H₂O. C: 4 = 4; H: 12 = 12; O: 14 = 8+6.',''),
    coefficient('Q7','Zn + HCl → ZnCl₂ + H₂',(1,2,1,1),'Atom counting','Zn + 2HCl → ZnCl₂ + H₂. Zn: 1 = 1; H: 2 = 2; Cl: 2 = 2.',''),
    dict(id='Q8', type='mcq', prompt='How many hydrogen and oxygen atoms are represented by 3H₂O?', answer='B', skill='Coefficients and subscripts',
         options=['A. 2 hydrogen and 3 oxygen','B. 6 hydrogen and 3 oxygen','C. 6 hydrogen and 6 oxygen','D. 3 hydrogen and 2 oxygen'], explanation='Multiply every atom by 3: H = 3×2 = 6; O = 3×1 = 3.'),
    dict(id='Q9', type='mcq', prompt='Why must a chemical equation be balanced?', answer='C', skill='Conservation of atoms',
         options=['A. Reactants and products must contain the same number of molecules.','B. All substances must have the same coefficient.','C. Each element must have the same number of atoms on both sides.','D. Reactants and products must contain the same number of substances.'], explanation='Atoms of each element are conserved. Molecule counts need not match.'),
    dict(id='Q10', type='mcq', prompt='A student changes H₂O to H₂O₂ while balancing an equation. Why is this invalid?', answer='D', skill='Coefficients and subscripts',
         options=['A. Subscripts can be changed only on the reactant side.','B. Every formula must contain the same number of oxygen atoms.','C. Coefficients change which elements a substance contains.','D. Changing the subscript changes the substance represented.'], explanation='Changing the subscript changes the substance. Change coefficients only.')]


def grade(questions, answers):
    """Validate every answer first. Well-formed but non-minimal tuples score zero."""
    if set(answers) != {q['id'] for q in questions}:
        raise ValueError('Answer every question before submitting.')
    results = []
    for q in questions:
        raw = answers[q['id']]
        if q['type'] == 'coefficients':
            if not isinstance(raw, str) or len(raw)>120 or not re.fullmatch(r'\s*[1-9]\d*(\s*,\s*[1-9]\d*)*\s*', raw):
                raise ValueError(f"{q['id']}: enter a positive whole number in every formula box, including 1.")
            value = tuple(int(x.strip()) for x in raw.split(','))
            if len(value) != len(q['answer']):
                raise ValueError(f"{q['id']}: enter {len(q['answer'])} coefficients in equation order.")
        else:
            if raw not in ('A','B','C','D'):
                raise ValueError(f"{q['id']}: select an answer.")
            value = raw
        results.append(dict(question=q['id'], answer=raw, correct=value == q['answer'], skill=q['skill']))
    return sum(r['correct'] for r in results), results


def worksheet(questions, teacher=False):
    text = TITLE + '\n\nName / learner ID: __________  Occurrence date/time (UTC): __________\n\n'
    text += 'Enter the smallest positive whole-number coefficients, including 1, in equation order.\n'
    for q in questions:
        text += f"\n{q['id']}. {q['prompt']}\n"
        if q['type'] == 'mcq':
            text += '\n'.join(q['options']) + '\n'
        text += 'Answer: ____________________\n'
        if teacher:
            text += f"KEY: {q['answer']}\n{q['explanation']}\nSkill: {q['skill']}\n"
    return text
