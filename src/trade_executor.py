import ccxt
import logging
from typing import Dict
from decimal import Decimal, ROUND_DOWN
import time
from wallet_position_tracker import WalletPositionTracker
from pybit.unified_trading import HTTP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TradeExecutor:
    def __init__(self, api_key: str, secret_key: str):
        self.client = HTTP(
            testnet=False,
            api_key=api_key,
            api_secret=secret_key
        )
        self.position_tracker = WalletPositionTracker(api_key, secret_key)

    def get_wallet_balance(self) -> float:
        try:
            response = self.client.get_wallet_balance(
                accountType="UNIFIED",
                coin="USDT"
            )
            
            logger.info(f"지갑 응답: {response}")
            
            if not response or 'retCode' not in response:
                logger.warning("API 응답 형식이 올바르지 않습니다")
                return 0.0
            
            if response['retCode'] != 0:
                logger.warning(f"API 오류: {response.get('retMsg', 'Unknown error')}")
                return 0.0
            
            result = response.get('result', {})
            wallet_list = result.get('list', [])
            
            if not wallet_list:
                logger.warning("지갑 정보가 비어있습니다")
                return 0.0
            
            # coin 배열에서 USDT 정보 찾기
            for wallet in wallet_list:
                coin_list = wallet.get('coin', [])
                for coin in coin_list:
                    if coin.get('coin') == 'USDT':
                        # 사용 가능한 잔고 필드 시도
                        balance_fields = [
                            'availableToWithdraw',  # 출금 가능 잔고
                            'walletBalance',        # 지갑 잔고
                            'equity'                # 평가 잔고
                        ]
                        
                        for field in balance_fields:
                            balance = coin.get(field)
                            if balance:
                                try:
                                    balance_float = float(balance)
                                    logger.info(f"USDT 잔고 ({field}): {balance_float}")
                                    return balance_float
                                except (ValueError, TypeError):
                                    continue
                                    
            logger.warning("USDT 잔고를 찾을 수 없습니다")
            return 0.0
            
        except Exception as e:
            logger.error(f"잔고 조회 중 에러 발생: {e}")
            return 0.0

    def get_current_price(self, symbol: str) -> float:
        """현재 가격 조회"""
        try:
            response = self.client.get_tickers(
                category="linear",
                symbol=symbol
            )
            if response and 'result' in response and 'list' in response['result'] and response['result']['list']:
                return float(response['result']['list'][0].get('lastPrice', '0'))
            return 0.0
        except Exception as e:
            logger.error(f"현재 가격 조회 중 에러 발생: {e}")
            return 0.0

    def execute_trade(self, symbol: str, trading_decision: Dict) -> bool:
        try:
            # 현재 포지션 확인
            current_position = self._get_current_position(symbol)
            current_side = current_position.get('side', 'NONE')
            position_size = float(current_position.get('size', '0'))
            
            logger.info(f"현재 포지션: {current_side}, 크기: {position_size}")
            
            position = trading_decision.get('position', 'HOLD')
            
            # 현재 포지션 상태에 따라 결정 수정
            if position == 'LONG->SHORT' and current_side == 'Sell':
                logger.info("이미 SHORT 포지션입니다. HOLD로 변경")
                return False
            elif position == 'SHORT->LONG' and current_side == 'Buy':
                logger.info("이미 LONG 포지션입니다. HOLD로 변경")
                return False
            
            # CLOSE 신호 처리
            if position == 'CLOSE' and position_size > 0:
                try:
                    # 청산 주문
                    close_side = "Sell" if current_side == "Buy" else "Buy"
                    
                    logger.info(f"포지션 청산 실행: {close_side}, 수량: {position_size}")
                    
                    self.client.place_order(
                        category="linear",
                        symbol=symbol,
                        side=close_side,
                        orderType="Market",
                        qty=f"{position_size:.3f}",
                        reduceOnly=True
                    )
                    
                    logger.info("포지션 청산 성공")
                    return True
                    
                except Exception as e:
                    logger.error(f"포지션 청산 중 오류: {e}")
                    return False
                
            # LONG->SHORT 또는 SHORT->LONG 처리
            if position in ['LONG->SHORT', 'SHORT->LONG'] and position_size > 0:
                try:
                    # 1. 현재 포지션 청산
                    close_side = "Sell" if current_side == "Buy" else "Buy"
                    
                    logger.info(f"기존 포지션 청산: {close_side}, 수량: {position_size}")
                    
                    self.client.place_order(
                        category="linear",
                        symbol=symbol,
                        side=close_side,
                        orderType="Market",
                        qty=f"{position_size:.3f}",
                        reduceOnly=True
                    )
                    
                    # 2. 잔고 업데이트를 기다림 (최대 5초)
                    time.sleep(2)  # 첫 번째 대기
                    
                    # 3. 레버리지 설정 (청산 후 설정)
                    leverage = int(trading_decision.get('leverage', 3))
                    try:
                        self.client.set_leverage(
                            category="linear",
                            symbol=symbol,
                            buyLeverage=str(leverage),
                            sellLeverage=str(leverage)
                        )
                        time.sleep(1)  # 레버리지 설정 후 추가 대기
                    except Exception as e:
                        if "110043" not in str(e):  # leverage not modified 에러는 무시
                            raise e
                    
                    # 4. 잔고 다시 확인
                    wallet_balance = float(self.get_wallet_balance())
                    current_price = self.get_current_price(symbol)
                    investment_ratio = float(trading_decision.get('investment_ratio', 0.1))
                    
                    # 5. 새로운 포지션 수량 계산 (여유있게 95%만 사용)
                    order_value = wallet_balance * investment_ratio * leverage * 0.95
                    order_quantity = round(order_value / current_price, 3)
                    
                    logger.info(f"새로운 포지션 계산: 잔고={wallet_balance}, 가격={current_price}, 수량={order_quantity}")
                    
                    if order_quantity >= 0.001:
                        # 6. 새 포지션 진입
                        new_side = "Sell" if position == "LONG->SHORT" else "Buy"
                        self.client.place_order(
                            category="linear",
                            symbol=symbol,
                            side=new_side,
                            orderType="Market",
                            qty=f"{order_quantity:.3f}",
                            isLeverage=1
                        )
                        logger.info(f"새로운 {new_side} 포지션 진입 성공: {order_quantity} BTC")
                        return True
                    else:
                        logger.warning(f"새로운 포지션 주문 수량이 너무 작음: {order_quantity}")
                        return False
                    
                except Exception as e:
                    logger.error(f"포지션 전환 중 오류: {e}")
                    return False
                
            # 기존 거래 로직...
            elif position in ['LONG', 'SHORT', 'LONG->SHORT', 'SHORT->LONG']:
                leverage = int(trading_decision.get('leverage', 3))
                investment_ratio = float(trading_decision.get('investment_ratio', 0.1))
                
                # 주문 수량 계산
                wallet_balance = self.get_wallet_balance()
                current_price = self.get_current_price(symbol)
                
                logger.info(f"잔고: {wallet_balance} USDT")
                logger.info(f"현재가: {current_price} USDT")
                logger.info(f"레버리지: {leverage}x")
                logger.info(f"투자비율: {investment_ratio}")
                
                order_value = wallet_balance * investment_ratio * leverage
                
                # 주문 수량을 3자리로 반올림 (바이비트 최소 단위: 0.001)
                order_quantity = round(order_value / current_price, 3)
                
                logger.info(f"계산된 주문 수량: {order_quantity} BTC")
                
                # 최소 주문 수량 확인 (0.001 BTC)
                if order_quantity < 0.001:
                    logger.warning(f"주문 수량이 최소 수량보다 작습니다: {order_quantity} < 0.001")
                    return False
                
                # 레버리지 설정 (이미 설정된 경우 무시)
                try:
                    self.client.set_leverage(
                        category="linear",
                        symbol=symbol,
                        buyLeverage=str(leverage),
                        sellLeverage=str(leverage)
                    )
                except Exception as e:
                    if "110043" not in str(e):  # leverage not modified 에러는 무시
                        logger.error(f"레버리지 설정 중 에러 발생: {e}")
                        return False
                
                # 포지션 처리 로직
                try:
                    if position == 'LONG' and current_side != 'Buy':
                        self.client.place_order(
                            category="linear",
                            symbol=symbol,
                            side="Buy",
                            orderType="Market",
                            qty=f"{order_quantity:.3f}",  # 3자리 소수점으로 포맷팅
                            isLeverage=1,  # 레버리지 거래 표시
                            reduceOnly=False
                        )
                        return True
                        
                    elif position in ['SHORT', 'LONG->SHORT'] and current_side != 'Sell':
                        # 숏 포지션 진입
                        if current_side == 'Buy':  # 롱 포지션 정리
                            self.client.place_order(
                                category="linear",
                                symbol=symbol,
                                side='Sell',
                                orderType="Market",
                                qty=str(position_size),
                                reduceOnly=True
                            )
                        # 숏 포지션 진입
                        self.client.place_order(
                            category="linear",
                            symbol=symbol,
                            side='Sell',
                            orderType="Market",
                            qty=str(order_quantity)
                        )
                        return True
                        
                    elif position in ['SHORT->LONG', 'CLOSE'] and current_side != 'NONE':
                        # 포지션 종료
                        side = 'Buy' if current_side == 'Sell' else 'Sell'
                        self.client.place_order(
                            category="linear",
                            symbol=symbol,
                            side=side,
                            orderType="Market",
                            qty=str(position_size),
                            reduceOnly=True
                        )
                        return True
                        
                    return False  # HOLD 또는 이미 원하는 포지션에 있는 경우
                    
                except Exception as e:
                    logger.error(f"주문 실행 중 에러 발생: {e}")
                    return False
                
            return False
            
        except Exception as e:
            logger.error(f"거래 실행 중 에러 발생: {e}")
            return False

    def _get_current_position(self, symbol: str) -> Dict:
        try:
            response = self.client.get_positions(
                category="linear",
                symbol=symbol
            )
            
            # 응답 데이터 검증
            if not response or 'result' not in response or 'list' not in response['result']:
                logger.warning("포지션 데이터가 없습니다")
                return self._empty_position()
            
            positions = response['result']['list']
            if not positions:
                logger.info("활성화된 포지션이 없습니다")
                return self._empty_position()
            
            position = positions[0]
            
            # 각 필드 개별적으로 안전하게 변환
            try:
                size = float(position.get('size', '0'))
            except (ValueError, TypeError):
                size = 0.0
            
            try:
                entry_price = float(position.get('avgPrice', '0'))
            except (ValueError, TypeError):
                entry_price = 0.0
            
            try:
                leverage = float(position.get('leverage', '0'))
            except (ValueError, TypeError):
                leverage = 0.0
            
            try:
                unrealised_pnl = float(position.get('unrealisedPnl', '0'))
            except (ValueError, TypeError):
                unrealised_pnl = 0.0
            
            return {
                'side': position.get('side', 'NONE'),
                'size': size,
                'entry_price': entry_price,
                'leverage': leverage,
                'unrealised_pnl': unrealised_pnl
            }
            
        except Exception as e:
            logger.error(f"포지션 조회 중 에러 발생: {e}")
            return self._empty_position()
        
    def _empty_position(self) -> Dict:
        """빈 포지션 정보 반환"""
        return {
            'side': 'NONE',
            'size': 0.0,
            'entry_price': 0.0,
            'leverage': 0.0,
            'unrealised_pnl': 0.0
        }

    def _set_leverage(self, symbol: str, leverage: int) -> bool:
        """레버리지 설정"""
        try:
            if leverage <= 0:  # leverage가 0이면 설정하지 않음
                return True
            self.client.set_leverage(
                category="linear",
                symbol=symbol,
                buy_leverage=str(leverage),
                sell_leverage=str(leverage)
            )
            return True
        except Exception as e:
            logger.error(f"레버리지 설정 중 에러 발생: {e}")
            return False

    def _get_available_balance(self) -> float:
        """사용 가능한 USDT 잔고 조회"""
        try:
            response = self.client.get_wallet_balance(
                accountType="UNIFIED",
                coin="USDT"
            )
            if response and 'result' in response and 'list' in response['result'] and response['result']['list']:
                return float(response['result']['list'][0].get('totalAvailableBalance', '0'))
            return 0.0
        except Exception as e:
            logger.error(f"잔고 조회 중 에러 발생: {e}")
            return 0.0

    def _calculate_contract_quantity(self, amount: float, price: float, leverage: int) -> float:
        """계약 수량 계산"""
        try:
            # 최소/최대 주문 수량 제한
            MIN_ORDER_SIZE = 0.001  # 최소 0.001 BTC
            MAX_MARKET_ORDER_SIZE = 119  # 최대 119 BTC (시장가 주문)
            
            # 계약 크기 (1 BTC = 1 계약)
            contract_size = 1.0
            
            # 레버리지를 고려한 실제 가능 수량 계산
            quantity = (amount * leverage) / (price * contract_size)
            
            # 최소/최대 제한 확인 및 조정
            if quantity < MIN_ORDER_SIZE:
                logger.warning(f"계산된 수량({quantity:.4f})이 최소 주문 수량({MIN_ORDER_SIZE})보다 작습니다. 최소값으로 조정합니다.")
                return MIN_ORDER_SIZE
            elif quantity > MAX_MARKET_ORDER_SIZE:
                logger.warning(f"계산된 수량({quantity:.4f})이 최대 시장가 주문 수량({MAX_MARKET_ORDER_SIZE})을 초과합니다. 최대값으로 조정합니다.")
                return MAX_MARKET_ORDER_SIZE
            
            # 소수점 3자리까지 반올림 (바이비트 최소 주문 단위)
            return float(Decimal(str(quantity)).quantize(Decimal('0.001'), rounding=ROUND_DOWN))
        except Exception as e:
            logger.error(f"계약 수량 계산 중 에러 발생: {e}")
            return MIN_ORDER_SIZE

    def _set_position_mode(self, symbol: str) -> bool:
        """포지션 모드 설정 (단일 포지션 모드)"""
        try:
            self.client.set_position_mode(False)  # False = One-Way Mode
            logger.info("단일 포지션 모드로 설정 완료")
            return True
        except Exception as e:
            logger.warning(f"포지션 모드 설정 중 에러 발생 (무시 가능): {e}")
            return False

    def _open_long_position(self, symbol: str, quantity: float) -> bool:
        """롱 포지션 진입"""
        try:
            # 포지션 모드 설정 추가
            self._set_position_mode(symbol)
            
            # 주문 파라미터 설정
            params = {
                'positionIdx': 0,  # 단일 포지션 모드
                'reduceOnly': False
            }
            
            self.client.create_market_buy_order(
                symbol,
                quantity,
                params
            )
            logger.info(f"롱 포지션 진입 성공: {quantity} 계약")
            return True
        except Exception as e:
            logger.error(f"롱 포지션 진입 중 에러 발생: {e}")
            return False

    def _open_short_position(self, symbol: str, quantity: float) -> bool:
        """숏 포지션 진입"""
        try:
            # 포지션 모드 설정 추가
            self._set_position_mode(symbol)
            
            # 주문 파라미터 설정
            params = {
                'positionIdx': 0,  # 단일 포지션 모드
                'reduceOnly': False
            }
            
            self.client.create_market_sell_order(
                symbol,
                quantity,
                params
            )
            logger.info(f"숏 포지션 진입 성공: {quantity} 계약")
            return True
        except Exception as e:
            logger.error(f"숏 포지션 진입 중 에러 발생: {e}")
            return False

    def _close_position(self, symbol: str, position: dict) -> bool:
        """포지션 청산"""
        try:
            if position['size'] == 0:
                logger.info("청산할 포지션이 없습니다.")
                return True
                
            # 포지션의 반대 방향으로 청산 주문
            params = {
                'positionIdx': 0,  # 단일 포지션 모드
                'reduceOnly': True
            }
            
            if position['side'].lower() == 'long':
                self.client.create_market_sell_order(
                    symbol,
                    position['size'],
                    params
                )
            else:  # short position
                self.client.create_market_buy_order(
                    symbol,
                    position['size'],
                    params
                )
                
            logger.info(f"포지션 종료 성공: {position['size']} 계약")
            return True
            
        except Exception as e:
            logger.error(f"포지션 종료 중 에러 발생: {e}")
            logger.error(f"포지션 정보: {position}")
            return False 

    def _validate_order_quantity(self, symbol: str, quantity: float) -> float:
        """주문 수량 검증 및 조정"""
        try:
            # 최소/최대 주문 수량 제한
            MIN_ORDER_SIZE = 0.001  # 최소 0.001 BTC
            MAX_MARKET_ORDER_SIZE = 119  # 최대 119 BTC (시장가 주문)
            
            if quantity < MIN_ORDER_SIZE:
                logger.warning(f"주문 수량({quantity})이 최소 주문 수량({MIN_ORDER_SIZE})보다 작습니다. 최소값으로 조정합니다.")
                return MIN_ORDER_SIZE
            elif quantity > MAX_MARKET_ORDER_SIZE:
                logger.warning(f"주문 수량({quantity})이 최대 시장가 주문 수량({MAX_MARKET_ORDER_SIZE})을 초과합니다. 최대값으로 조정합니다.")
                return MAX_MARKET_ORDER_SIZE
            
            return quantity
        except Exception as e:
            logger.error(f"주문 수량 검증 중 에러 발생: {e}")
            return MIN_ORDER_SIZE

    def _wait_for_order_completion(self, order_id: str, symbol: str, timeout: int = 10) -> bool:
        """주문 완료 대기"""
        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                order = self.client.fetch_order(order_id, symbol)
                if order['status'] in ['closed', 'filled']:
                    return True
                elif order['status'] in ['canceled', 'expired', 'rejected']:
                    logger.error(f"주문 실패: {order['status']}")
                    return False
                time.sleep(0.5)
            
            logger.error("주문 완료 대기 시간 초과")
            return False
        except Exception as e:
            logger.error(f"주문 상태 확인 중 에러 발생: {e}")
            return False

    def _handle_order_error(self, e: Exception, action: str) -> bool:
        """주문 에러 처리"""
        error_msg = str(e)
        if "insufficient balance" in error_msg.lower():
            logger.error(f"{action} 실패: 잔고 부족")
        elif "minimum notional" in error_msg.lower():
            logger.error(f"{action} 실패: 최소 주문 금액 미달")
        elif "maximum notional" in error_msg.lower():
            logger.error(f"{action} 실패: 최대 주문 금액 초과")
        else:
            logger.error(f"{action} 실패: {error_msg}")
        return False 