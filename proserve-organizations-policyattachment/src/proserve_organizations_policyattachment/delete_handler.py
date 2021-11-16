# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
from logging import Logger
from typing import Any, MutableMapping

import backoff
from cloudformation_cli_python_lib import (
    OperationStatus,
    ProgressEvent,
    SessionProxy,
    exceptions,
)

from .models import ResourceModel
from .utilities import progress_404


def _delete_handler(
    session: SessionProxy,
    model: ResourceModel,
    callback_context: MutableMapping[str, Any],
    logger: Logger,
) -> ProgressEvent:

    org_client = session.client("organizations")

    @backoff.on_exception(
        backoff.constant,
        (
            org_client.exceptions.ConcurrentModificationException,
            org_client.exceptions.TooManyRequestsException,
        ),
        jitter=backoff.random_jitter,
        max_time=40,
        interval=1,
    )
    def detach_policy(policy_id: str, target_id: str) -> dict:
        return org_client.detach_policy(PolicyId=policy_id, TargetId=target_id)

    try:
        response = detach_policy(model.PolicyId, model.TargetId)
        logger.debug(response)
    except org_client.exceptions.PolicyNotFoundException as e:
        logger.error(f"Policy {model.PolicyId} does not exist")
        return progress_404(f"Policy {model.PolicyId} does not exist")
    except org_client.exceptions.TargetNotFoundException as e:
        logger.error(f"Target {model.TargetId} does not exist")
        return progress_404(f"Target {model.PolicyId} does not exist")
    except org_client.exceptions.PolicyNotAttachedException as e:
        logger.error(
            f"Policy {model.PolicyId} is not attached to Target {model.TargetId}"
        )
        return progress_404(
            f"Policy {model.PolicyId} is not attached to Target {model.TargetId}"
        )
    except Exception as e:
        logger.error("Could not detach Policy")
        raise exceptions.InternalFailure(f"{e}")

    progress: ProgressEvent = ProgressEvent(
        status=OperationStatus.SUCCESS,
    )
    logger.debug(f"Successfully deleted policy {model.PolicyId}.")
    return progress
