# language: pt
Funcionalidade: Pagamento
  Cenário: Pagar com cartão
    Dado um carrinho
    Quando pago
    Então a encomenda é confirmada
