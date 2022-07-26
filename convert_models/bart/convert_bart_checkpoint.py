from convert_models.bart.modeling_lsg_bart import *
from convert_models.conversion_utils import ConversionScript

class BartConversionScript(ConversionScript):

    _ARCHITECTURE_TYPE_DICT = {
        "BartModel": ("LSGBartModel", LSGBartModel),
        "BartForConditionalGeneration": ("LSGBartForConditionalGeneration", LSGBartForConditionalGeneration),
        "BartForCausalLM": ("LSGBartForCausalLM", LSGBartForCausalLM),
        "BartForQuestionAnswering": ("LSGBartForQuestionAnswering", LSGBartForQuestionAnswering),
        "BartForSequenceClassification": ("LSGBartForSequenceClassification", LSGBartForSequenceClassification),
        }
    _ARCHITECTURE_TYPE_DICT = {**{"LSG" + k: v for k, v in _ARCHITECTURE_TYPE_DICT.items()}, **_ARCHITECTURE_TYPE_DICT}

    _BASE_ARCHITECTURE_TYPE = "BartModel"
    _DEFAULT_ARCHITECTURE_TYPE = "BartForConditionalGeneration"
    _CONFIG_MODULE = LSGBartConfig

    _DEFAULT_CONFIG_POSITIONAL_OFFSET = 0
    _DEFAULT_POSITIONAL_OFFSET = 2

    def __init__(
        self, 
        initial_model, 
        model_name, 
        max_sequence_length, 
        architecture, 
        random_global_init, 
        global_positional_stride, 
        keep_first_global_token, 
        resize_lsg, 
        model_kwargs, 
        config,
        seed
        ):
        super().__init__(
            initial_model, 
            model_name, 
            max_sequence_length, 
            architecture, 
            random_global_init, 
            global_positional_stride, 
            keep_first_global_token, 
            resize_lsg, 
            model_kwargs, 
            config,
            seed
        )

    def get_module(self, model, is_base_architecture):
        if is_base_architecture:
            return model
        return model.model

    def update_global_randomly(self, module_prefix, bos_id, stride, keep_first_global):

        import torch
        from torch.distributions.multivariate_normal import MultivariateNormal

        u = module_prefix.shared.weight.clone()
        cov = torch.cov(u.T)
        m = MultivariateNormal(u.mean(dim=0), cov)
        w = m.sample((512,))
        w[0] = u[bos_id]

        positions = module_prefix.encoder.embed_positions.weight.clone()[self._DEFAULT_POSITIONAL_OFFSET:] 
        positions = self.order_positions(positions, stride)
        
        if keep_first_global:
            module_prefix.encoder.global_embeddings.weight.data[1:] = (w + positions)[1:]
        else:
            module_prefix.encoder.global_embeddings.weight.data = w + positions

    def update_global(self, module_prefix, bos_id, mask_id, stride, keep_first_global):

        u = module_prefix.shared.weight.clone()
        positions = module_prefix.encoder.embed_positions.weight.clone()[self._DEFAULT_POSITIONAL_OFFSET:]
        positions = self.order_positions(positions, stride)

        positions[0] += u[bos_id]
        positions[1:] += u[mask_id].unsqueeze(0)

        if keep_first_global:
            module_prefix.encoder.global_embeddings.weight.data[1:] = positions[self._DEFAULT_POSITIONAL_OFFSET:]
        else:
            module_prefix.encoder.global_embeddings.weight.data = positions

    def update_positions(self, module_prefix, max_pos):

        # Encoder
        position_embeddings_weights = module_prefix.encoder.embed_positions.weight.clone()
        current_max_position = position_embeddings_weights.size()[0]

        new_position_embeddings_weights = torch.cat([
            position_embeddings_weights[:self._DEFAULT_POSITIONAL_OFFSET]] + 
            [position_embeddings_weights[self._DEFAULT_POSITIONAL_OFFSET:] for _ in range(max_pos//current_max_position + 1)], 
            dim=0)[:max_pos + self._DEFAULT_POSITIONAL_OFFSET]

        #processed_module.encoder.embed_positions.position_ids = torch.arange(max_pos + 2, device=processed_module.encoder.embed_positions.position_ids.device).unsqueeze(0)
        module_prefix.encoder.embed_positions.weight.data = new_position_embeddings_weights

        # Decoder
        position_embeddings_weights = module_prefix.decoder.embed_positions.weight.clone()
        current_max_position = position_embeddings_weights.size()[0]

        new_position_embeddings_weights = torch.cat([
            position_embeddings_weights[:self._DEFAULT_POSITIONAL_OFFSET]] + 
            [position_embeddings_weights[self._DEFAULT_POSITIONAL_OFFSET:] for _ in range(max_pos//current_max_position + 1)], 
            dim=0)[:max_pos + self._DEFAULT_POSITIONAL_OFFSET]

        module_prefix.decoder.embed_positions.weight.data = new_position_embeddings_weights