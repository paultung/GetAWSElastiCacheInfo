"""Custom exceptions for AWS ElastiCache client."""

from typing import Optional


class AWSBaseError(Exception):
    """Base exception for AWS-related errors."""

    def __init__(
        self,
        message: str,
        suggestion: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        """Initialize AWS error.

        Args:
            message: Error message in Chinese
            suggestion: Suggested solution in Chinese
            original_error: Original exception for debugging
        """
        self.message = message
        self.suggestion = suggestion
        self.original_error = original_error
        super().__init__(self.message)

    def __str__(self) -> str:
        """Format error message."""
        msg = self.message
        if self.suggestion:
            msg += f"\n建議：{self.suggestion}"
        return msg


class AWSPermissionError(AWSBaseError):
    """Exception raised when AWS permissions are insufficient."""

    def __init__(
        self,
        operation: str,
        original_error: Optional[Exception] = None
    ):
        """Initialize permission error.

        Args:
            operation: AWS operation that failed
            original_error: Original exception
        """
        message = f"權限不足：您的 AWS Profile 沒有 {operation} 權限"
        suggestion = "請確認 IAM 角色具有 elasticache:Describe* 權限"
        super().__init__(message, suggestion, original_error)


class AWSInvalidParameterError(AWSBaseError):
    """Exception raised when AWS API parameters are invalid."""

    def __init__(
        self,
        parameter: str,
        value: str,
        original_error: Optional[Exception] = None
    ):
        """Initialize invalid parameter error.

        Args:
            parameter: Parameter name
            value: Invalid parameter value
            original_error: Original exception
        """
        message = f"無效的參數：{parameter} = '{value}'"
        suggestion = "請檢查參數值是否正確"
        super().__init__(message, suggestion, original_error)


class AWSAPIError(AWSBaseError):
    """Exception raised for general AWS API errors."""

    def __init__(
        self,
        operation: str,
        error_code: str,
        error_message: str,
        original_error: Optional[Exception] = None
    ):
        """Initialize API error.

        Args:
            operation: AWS operation that failed
            error_code: AWS error code
            error_message: AWS error message
            original_error: Original exception
        """
        message = f"AWS API 錯誤：{operation} 失敗 ({error_code}): {error_message}"
        suggestion = "請檢查 AWS 服務狀態或稍後重試"
        super().__init__(message, suggestion, original_error)


class AWSCredentialsError(AWSBaseError):
    """Exception raised when AWS credentials are missing or invalid."""

    def __init__(self, original_error: Optional[Exception] = None):
        """Initialize credentials error.

        Args:
            original_error: Original exception
        """
        message = "AWS 認證錯誤：找不到有效的 AWS 認證"
        suggestion = (
            "請確認已設定 AWS CLI 或環境變數 (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)"
        )
        super().__init__(message, suggestion, original_error)


class AWSConnectionError(AWSBaseError):
    """Exception raised when connection to AWS fails."""

    def __init__(
        self,
        region: str,
        original_error: Optional[Exception] = None
    ):
        """Initialize connection error.

        Args:
            region: AWS region
            original_error: Original exception
        """
        message = f"AWS 連線錯誤：無法連線到 {region}"
        suggestion = "請檢查網路連線和 Region 名稱是否正確"
        super().__init__(message, suggestion, original_error)
