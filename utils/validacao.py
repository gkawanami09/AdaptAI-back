import re

def validar_senha_forte(senha : str):
    if len(senha) < 8:
        return False, 'A senha deve ter pelo menos 8 caracteres'

    if not re.search(r'[A-Z]', senha):
        return False, 'A senha deve ter pelo menos uma letra maiúscula'

    if not re.search(r'[a-z]', senha):
        return False, 'A senha deve ter pelo menos uma letra minúscula'

    if not re.search(r'[0-9]', senha):
        return False, 'A senha deve ter pelo menos um número'

    if not re.search(r'[!@#$%^&*(),.?\":{}|<>_\-+=]', senha):
        return False, 'A senha deve ter pelo menos um caractere especial'

    return True, 'Senha válida'
    