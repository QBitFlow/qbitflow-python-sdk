"""Field types of the open enums: a known value decodes to the enum member, an unknown string is
kept raw (``Union[Enum, str]``)."""

from typing import Annotated, Union

from ._base import open_enum
from .enums import (
    AccountingEventType,
    ActionRequired,
    AttemptStatus,
    BillingFailureReason,
    BillingOutcome,
    BillingStage,
    CancellationReason,
    Chain,
    CheckoutSessionStatusValue,
    CombinedPaymentSource,
    Credential,
    DurationUnit,
    EndpointDisabledReason,
    EventType,
    FailureCategory,
    FailureKind,
    FeeLineType,
    InvitationStatus,
    LedgerEntryType,
    NotRefundableReason,
    RefundInitiator,
    RefundStatus,
    Role,
    SubscriptionStatus,
    TransactionType,
    TransferType,
    WebhookPayloadVersion,
)

AccountingEventTypeT = Annotated[Union[AccountingEventType, str], open_enum(AccountingEventType)]
ActionRequiredT = Annotated[Union[ActionRequired, str], open_enum(ActionRequired)]
AttemptStatusT = Annotated[Union[AttemptStatus, str], open_enum(AttemptStatus)]
BillingFailureReasonT = Annotated[Union[BillingFailureReason, str], open_enum(BillingFailureReason)]
BillingOutcomeT = Annotated[Union[BillingOutcome, str], open_enum(BillingOutcome)]
BillingStageT = Annotated[Union[BillingStage, str], open_enum(BillingStage)]
CancellationReasonT = Annotated[Union[CancellationReason, str], open_enum(CancellationReason)]
ChainT = Annotated[Union[Chain, str], open_enum(Chain)]
CheckoutSessionStatusValueT = Annotated[
    Union[CheckoutSessionStatusValue, str], open_enum(CheckoutSessionStatusValue)
]
CombinedPaymentSourceT = Annotated[
    Union[CombinedPaymentSource, str], open_enum(CombinedPaymentSource)
]
CredentialT = Annotated[Union[Credential, str], open_enum(Credential)]
DurationUnitT = Annotated[Union[DurationUnit, str], open_enum(DurationUnit)]
EndpointDisabledReasonT = Annotated[
    Union[EndpointDisabledReason, str], open_enum(EndpointDisabledReason)
]
EventTypeT = Annotated[Union[EventType, str], open_enum(EventType)]
FailureCategoryT = Annotated[Union[FailureCategory, str], open_enum(FailureCategory)]
FailureKindT = Annotated[Union[FailureKind, str], open_enum(FailureKind)]
FeeLineTypeT = Annotated[Union[FeeLineType, str], open_enum(FeeLineType)]
InvitationStatusT = Annotated[Union[InvitationStatus, str], open_enum(InvitationStatus)]
LedgerEntryTypeT = Annotated[Union[LedgerEntryType, str], open_enum(LedgerEntryType)]
NotRefundableReasonT = Annotated[Union[NotRefundableReason, str], open_enum(NotRefundableReason)]
RefundInitiatorT = Annotated[Union[RefundInitiator, str], open_enum(RefundInitiator)]
RefundStatusT = Annotated[Union[RefundStatus, str], open_enum(RefundStatus)]
RoleT = Annotated[Union[Role, str], open_enum(Role)]
SubscriptionStatusT = Annotated[Union[SubscriptionStatus, str], open_enum(SubscriptionStatus)]
TransactionTypeT = Annotated[Union[TransactionType, str], open_enum(TransactionType)]
TransferTypeT = Annotated[Union[TransferType, str], open_enum(TransferType)]
WebhookPayloadVersionT = Annotated[
    Union[WebhookPayloadVersion, str], open_enum(WebhookPayloadVersion)
]
